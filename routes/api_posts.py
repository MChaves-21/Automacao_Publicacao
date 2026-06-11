"""routes/api_posts.py — CRUD de posts com fluxo draft→review→approved→published."""
import uuid
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from core.models import Post, PostStatus, UserRole, db
from core.audit import log_action

posts_bp = Blueprint("posts", __name__, url_prefix="/api/posts")


def _bad(msg, code=400): return jsonify({"error": msg}), code
def _forbidden(): return jsonify({"error": "Permissão negada."}), 403


# ── Listar posts ──────────────────────────────────────────────────────────────

@posts_bp.get("")
@login_required
def list_posts():
    status = request.args.get("status")
    q = Post.query.order_by(Post.created_at.desc())
    if not current_user.is_admin:
        if current_user.can_review:
            q = q.filter(Post.status.in_([PostStatus.PENDING, PostStatus.APPROVED, PostStatus.PUBLISHED]))
        else:
            q = q.filter(Post.author_id == current_user.id)
    if status:
        q = q.filter(Post.status == status)
    return jsonify([p.to_dict() for p in q.limit(100)])


@posts_bp.get("/pending")
@login_required
def list_pending():
    if not current_user.can_review:
        return _forbidden()
    posts = Post.query.filter_by(status=PostStatus.PENDING).order_by(Post.created_at).all()
    return jsonify([p.to_dict() for p in posts])


@posts_bp.get("/calendar")
@login_required
def calendar_posts():
    """Posts com data agendada para o calendário visual."""
    posts = Post.query.filter(
        Post.scheduled_at.isnot(None),
        Post.status.in_([PostStatus.APPROVED, PostStatus.PUBLISHED, PostStatus.DRAFT, PostStatus.PENDING])
    ).order_by(Post.scheduled_at).all()
    return jsonify([p.to_dict() for p in posts])


# ── Criar post ────────────────────────────────────────────────────────────────

@posts_bp.post("")
@login_required
def create_post():
    data = request.get_json(silent=True) or {}
    content    = (data.get("content") or "").strip()
    platforms  = data.get("platforms") or []
    image_url  = data.get("image_url") or None
    image_prompt = data.get("image_prompt") or None
    scheduled  = data.get("scheduled_at") or None
    ab_test    = data.get("ab_test", False)
    submit     = data.get("submit_for_review", False)
    adapted    = data.get("adapted_content")

    if not content: return _bad("Conteúdo obrigatório.")
    if not platforms: return _bad("Selecione ao menos uma plataforma.")

    run_at = None
    if scheduled:
        try: run_at = datetime.strptime(scheduled, "%Y-%m-%dT%H:%M")
        except ValueError: return _bad("Formato de data inválido.")

    # Status inicial
    if current_user.can_publish_direct:
        status = PostStatus.APPROVED
    elif submit:
        status = PostStatus.PENDING
    else:
        status = PostStatus.DRAFT

    # A/B Testing
    if ab_test:
        group_id = str(uuid.uuid4())
        post_a = Post(author_id=current_user.id, content=content, platforms=platforms,
                      image_url=image_url, image_prompt=image_prompt,
                      adapted_content=adapted, status=status, scheduled_at=run_at,
                      ab_variant="A", ab_group_id=group_id)
        post_b = Post(author_id=current_user.id, content=content, platforms=platforms,
                      image_url=image_url, image_prompt=image_prompt,
                      status=status, scheduled_at=run_at, ab_variant="B", ab_group_id=group_id)
        db.session.add_all([post_a, post_b])
        db.session.commit()
        log_action("create_post_ab", "post", post_a.id, {"group_id": group_id, "platforms": platforms})
        _notify_if_pending(post_a, status)
        return jsonify({"a": post_a.to_dict(), "b": post_b.to_dict()}), 201

    post = Post(author_id=current_user.id, content=content, platforms=platforms,
                image_url=image_url, image_prompt=image_prompt,
                adapted_content=adapted, status=status, scheduled_at=run_at)
    db.session.add(post)
    db.session.commit()
    log_action("create_post", "post", post.id, {"status": status, "platforms": platforms})
    _notify_if_pending(post, status)

    return jsonify(post.to_dict()), 201


# ── Ações de aprovação ────────────────────────────────────────────────────────

@posts_bp.post("/<int:post_id>/submit")
@login_required
def submit_for_review(post_id: int):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id and not current_user.is_admin:
        return _forbidden()
    if post.status != PostStatus.DRAFT:
        return _bad("Apenas rascunhos podem ser enviados para revisão.")
    post.status = PostStatus.PENDING
    db.session.commit()
    log_action("submit_for_review", "post", post_id)
    _notify_reviewers(post)
    return jsonify(post.to_dict())


@posts_bp.post("/<int:post_id>/approve")
@login_required
def approve_post(post_id: int):
    if not current_user.can_review:
        return _forbidden()
    post = Post.query.get_or_404(post_id)
    if post.status != PostStatus.PENDING:
        return _bad("Apenas posts pendentes podem ser aprovados.")
    post.status = PostStatus.APPROVED
    post.reviewer_id = current_user.id
    db.session.commit()
    log_action("approve_post", "post", post_id)
    _notify_approved(post)

    if not post.scheduled_at:
        return _publish_post(post)
    return jsonify(post.to_dict())


@posts_bp.post("/<int:post_id>/reject")
@login_required
def reject_post(post_id: int):
    if not current_user.can_review:
        return _forbidden()
    post = Post.query.get_or_404(post_id)
    reason = (request.get_json(silent=True) or {}).get("reason", "Sem motivo informado.")
    post.status = PostStatus.REJECTED
    post.rejection_reason = reason
    post.reviewer_id = current_user.id
    db.session.commit()
    log_action("reject_post", "post", post_id, {"reason": reason})
    try:
        from core.email_service import notify_rejected
        notify_rejected(post.author.email, reason)
    except Exception: pass
    return jsonify(post.to_dict())


@posts_bp.post("/<int:post_id>/publish")
@login_required
def publish_post_now(post_id: int):
    if not current_user.can_publish_direct:
        return _forbidden()
    post = Post.query.get_or_404(post_id)
    return _publish_post(post)


@posts_bp.delete("/<int:post_id>")
@login_required
def delete_post(post_id: int):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id and not current_user.is_admin:
        return _forbidden()
    db.session.delete(post)
    db.session.commit()
    log_action("delete_post", "post", post_id)
    return jsonify({"ok": True})


# ── Helpers internos ──────────────────────────────────────────────────────────

def _publish_post(post: Post):
    from core.ai_processor import adapt_content
    from core.publishers import PUBLISHERS

    try:
        adapted = (post.adapted_content
                   or {k: v.to_dict() for k, v in
                       adapt_content(post.content, image_url=post.image_url,
                                     platforms=post.platforms).items()})
    except Exception as exc:
        post.status = PostStatus.FAILED
        db.session.commit()
        return jsonify({"error": str(exc)}), 500

    results, errors = [], []
    for platform in post.platforms:
        pub = PUBLISHERS.get(platform)
        if not pub: continue
        try:
            from core.ai_processor import AdaptedContent
            content_data = adapted.get(platform) or {}
            if isinstance(content_data, dict):
                ac = AdaptedContent(
                    platform=platform,
                    text=content_data.get("text", ""),
                    hashtags=content_data.get("hashtags", []),
                    is_thread=content_data.get("is_thread", False),
                    thread_parts=content_data.get("thread_parts"),
                )
            else:
                ac = content_data
            r = pub(ac, image_url=post.image_url)
            results.append(r)
        except Exception as exc:
            errors.append({"platform": platform, "error": str(exc)})
            try:
                from core.email_service import notify_failed
                notify_failed(post.author.email, platform, str(exc))
            except Exception: pass

    post.status = PostStatus.PUBLISHED if results else PostStatus.FAILED
    post.published_at = datetime.utcnow()
    post.results = {"results": results, "errors": errors}
    db.session.commit()
    log_action("publish_post", "post", post.id, {"platforms": post.platforms, "ok": len(results), "err": len(errors)})

    # Webhooks + Slack
    try:
        from core.webhooks import fire
        event = "post.published" if results else "post.failed"
        fire(event, post=post)
    except Exception:
        pass

    try:
        from core.email_service import notify_published
        if results:
            notify_published(post.author.email, [r["platform"] for r in results])
    except Exception: pass

    return jsonify({"post": post.to_dict(), "results": results, "errors": errors})


def _notify_if_pending(post: Post, status: str):
    if status == PostStatus.PENDING:
        _notify_reviewers(post)


def _notify_reviewers(post: Post):
    try:
        from core.webhooks import fire
        fire("post.pending", post=post)
    except Exception:
        pass
    try:
        from core.models import User, UserRole
        from core.email_service import notify_pending_review
        reviewers = User.query.filter(
            User.role.in_([UserRole.ADMIN, UserRole.REVIEWER]),
            User.is_active == True
        ).all()
        for r in reviewers:
            notify_pending_review(r.email, post.id, post.author.username, post.content)
    except Exception: pass


def _notify_approved(post: Post):
    try:
        from core.webhooks import fire
        fire("post.approved", post=post)
    except Exception:
        pass
    try:
        from core.email_service import notify_approved
        notify_approved(post.author.email, post.id)
    except Exception: pass
