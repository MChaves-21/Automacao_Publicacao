"""routes/api_integrations.py — Brand Voice, RSS, Webhooks, Upload, Export, Score, Recycling."""
import os
import uuid
from datetime import datetime
from flask import Blueprint, Response, jsonify, request, send_file, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

integrations_bp = Blueprint("integrations", __name__, url_prefix="/api")


def _bad(msg, code=400): return jsonify({"error": msg}), code
def _forbidden():        return jsonify({"error": "Permissão negada."}), 403


# ── Brand Voice ───────────────────────────────────────────────────────────────

@integrations_bp.get("/brand-voice")
@login_required
def list_brand_voices():
    from core.models import BrandVoice
    voices = BrandVoice.query.order_by(BrandVoice.created_at.desc()).all()
    return jsonify([v.to_dict() for v in voices])


@integrations_bp.post("/brand-voice")
@login_required
def create_brand_voice():
    from core.models import BrandVoice, db
    from core.audit import log_action
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _bad("Nome obrigatório.")

    # Desativar a voz anterior antes de criar nova
    if data.get("is_active"):
        BrandVoice.query.update({"is_active": False})

    bv = BrandVoice(
        name=name, tone=data.get("tone", "profissional"),
        description=data.get("description"), keywords=data.get("keywords", []),
        avoid_words=data.get("avoid_words", []), example_post=data.get("example_post"),
        is_active=data.get("is_active", True), author_id=current_user.id,
    )
    db.session.add(bv); db.session.commit()
    log_action("create_brand_voice", "brand_voice", bv.id, {"name": name})
    return jsonify(bv.to_dict()), 201


@integrations_bp.patch("/brand-voice/<int:vid>")
@login_required
def update_brand_voice(vid: int):
    from core.models import BrandVoice, db
    bv = BrandVoice.query.get_or_404(vid)
    data = request.get_json(silent=True) or {}
    if "name"         in data: bv.name         = data["name"]
    if "tone"         in data: bv.tone         = data["tone"]
    if "description"  in data: bv.description  = data["description"]
    if "keywords"     in data: bv.keywords      = data["keywords"]
    if "avoid_words"  in data: bv.avoid_words   = data["avoid_words"]
    if "example_post" in data: bv.example_post  = data["example_post"]
    if data.get("is_active"):
        BrandVoice.query.filter(BrandVoice.id != vid).update({"is_active": False})
        bv.is_active = True
    elif "is_active" in data:
        bv.is_active = data["is_active"]
    db.session.commit()
    return jsonify(bv.to_dict())


@integrations_bp.delete("/brand-voice/<int:vid>")
@login_required
def delete_brand_voice(vid: int):
    from core.models import BrandVoice, db
    bv = BrandVoice.query.get_or_404(vid)
    db.session.delete(bv); db.session.commit()
    return jsonify({"ok": True})


# ── RSS Feeds ─────────────────────────────────────────────────────────────────

@integrations_bp.get("/rss")
@login_required
def list_rss():
    from core.models import RssFeed
    return jsonify([f.to_dict() for f in RssFeed.query.order_by(RssFeed.created_at.desc()).all()])


@integrations_bp.post("/rss")
@login_required
def create_rss():
    from core.models import RssFeed, db
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url  = (data.get("url")  or "").strip()
    if not name or not url:
        return _bad("Nome e URL são obrigatórios.")

    feed = RssFeed(
        name=name, url=url,
        platforms=data.get("platforms", ["twitter", "linkedin"]),
        interval_hours=int(data.get("interval_hours", 6)),
        is_active=data.get("is_active", True),
        author_id=current_user.id,
    )
    db.session.add(feed); db.session.commit()

    try:
        from core.rss_monitor import refresh_rss_schedule
        from web_app import app as flask_app
        from core.scheduler import scheduler
        refresh_rss_schedule(scheduler, flask_app, feed.id)
    except Exception:
        pass

    return jsonify(feed.to_dict()), 201


@integrations_bp.post("/rss/<int:fid>/check")
@login_required
def check_rss_now(fid: int):
    from core.rss_monitor import check_feed
    created = check_feed(fid)
    return jsonify({"created": len(created), "posts": created})


@integrations_bp.delete("/rss/<int:fid>")
@login_required
def delete_rss(fid: int):
    from core.models import RssFeed, db
    feed = RssFeed.query.get_or_404(fid)
    db.session.delete(feed); db.session.commit()
    return jsonify({"ok": True})


# ── Webhooks ──────────────────────────────────────────────────────────────────

@integrations_bp.get("/webhooks")
@login_required
def list_webhooks():
    from core.models import Webhook
    return jsonify([w.to_dict() for w in Webhook.query.order_by(Webhook.created_at.desc()).all()])


@integrations_bp.post("/webhooks")
@login_required
def create_webhook():
    from core.models import Webhook, db
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url  = (data.get("url")  or "").strip()
    if not name or not url:
        return _bad("Nome e URL são obrigatórios.")

    secret = str(uuid.uuid4()).replace("-", "")
    hook = Webhook(
        name=name, url=url,
        events=data.get("events", ["post.published", "post.failed"]),
        secret=secret, is_active=True, author_id=current_user.id,
    )
    db.session.add(hook); db.session.commit()
    result = hook.to_dict()
    result["secret"] = secret  # retornar só na criação
    return jsonify(result), 201


@integrations_bp.post("/webhooks/<int:wid>/test")
@login_required
def test_webhook(wid: int):
    from core.models import Webhook
    from core.webhooks import dispatch_event
    hook = Webhook.query.get_or_404(wid)
    results = dispatch_event("webhook.test", {"webhook_id": wid, "message": "Teste de conexão MktAuto"})
    return jsonify({"results": results})


@integrations_bp.delete("/webhooks/<int:wid>")
@login_required
def delete_webhook(wid: int):
    from core.models import Webhook, db
    hook = Webhook.query.get_or_404(wid)
    db.session.delete(hook); db.session.commit()
    return jsonify({"ok": True})


# ── Upload de imagem ──────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@integrations_bp.post("/upload/image")
@login_required
def upload_image():
    if "file" not in request.files:
        return _bad("Campo 'file' não encontrado.")

    file = request.files["file"]
    if not file.filename or not _allowed_file(file.filename):
        return _bad("Tipo de arquivo não suportado. Use PNG, JPG, GIF ou WebP.")

    ext      = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    # Cloudinary (se configurado)
    from config import config
    if config.cloudinary_url:
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(cloudinary_url=config.cloudinary_url)
            result = cloudinary.uploader.upload(file, public_id=filename.rsplit(".", 1)[0])
            return jsonify({"url": result["secure_url"], "provider": "cloudinary"})
        except Exception as exc:
            return _bad(f"Erro ao fazer upload para Cloudinary: {exc}", 500)

    # Armazenamento local
    upload_folder = os.path.join(current_app.root_path, "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))
    return jsonify({"url": f"/uploads/{filename}", "provider": "local"})


# ── Export ────────────────────────────────────────────────────────────────────

@integrations_bp.get("/export/posts.csv")
@login_required
def export_csv():
    from core.models import Post
    from core.exporter import export_posts_csv
    posts = [p.to_dict() for p in Post.query.order_by(Post.created_at.desc()).limit(1000).all()]
    csv_bytes = export_posts_csv(posts)
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=posts.csv"},
    )


@integrations_bp.get("/export/report.html")
@login_required
def export_report():
    from core.models import Post
    from core.scheduler import read_log
    from core.exporter import export_report_html
    from routes.api import get_stats

    with current_app.test_request_context():
        from flask_login import login_user
        login_user(current_user)

    posts   = [p.to_dict() for p in Post.query.order_by(Post.created_at.desc()).limit(50).all()]
    entries = read_log(limit=200)

    from core.scheduler import list_jobs
    from core.models import PostStatus
    published = sum(len(e.get("results", [])) for e in entries)
    errors    = sum(len(e.get("errors",   [])) for e in entries)
    pending   = Post.query.filter_by(status=PostStatus.PENDING).count()
    by_plat: dict[str, int] = {}
    for e in entries:
        for r in e.get("results", []):
            p = r.get("platform", ""); by_plat[p] = by_plat.get(p, 0) + 1

    stats = {"published": published, "errors": errors,
             "pending": pending, "sessions": len(entries), "by_platform": by_plat}

    html = export_report_html(stats, posts, entries)
    return Response(html, mimetype="text/html",
                    headers={"Content-Disposition": "inline; filename=relatorio.html"})


# ── Score de performance ──────────────────────────────────────────────────────

@integrations_bp.post("/score")
@login_required
def score_post():
    from core.brand_voice import score_post as compute_score
    data      = request.get_json(silent=True) or {}
    content   = (data.get("content") or "").strip()
    platforms = data.get("platforms") or ["twitter", "instagram", "linkedin"]
    if not content:
        return _bad("Conteúdo obrigatório.")
    try:
        result = compute_score(content, platforms)
        return jsonify(result)
    except Exception as exc:
        return _bad(str(exc), 500)


# ── Reciclagem ────────────────────────────────────────────────────────────────

@integrations_bp.get("/recycle/candidates")
@login_required
def recycle_candidates():
    from core.recycler import find_recyclable
    days  = int(request.args.get("min_days", 30))
    limit = int(request.args.get("limit", 10))
    return jsonify(find_recyclable(limit=limit, min_age_days=days))


@integrations_bp.post("/recycle/<int:post_id>")
@login_required
def recycle_post(post_id: int):
    from core.recycler import recycle_post as do_recycle
    data      = request.get_json(silent=True) or {}
    variation = data.get("variation", True)
    run_at    = None
    if data.get("run_at"):
        try: run_at = datetime.strptime(data["run_at"], "%Y-%m-%dT%H:%M")
        except ValueError: return _bad("Formato de data inválido.")
    try:
        new_post = do_recycle(post_id, variation=variation, run_at=run_at)
        return jsonify(new_post), 201
    except Exception as exc:
        return _bad(str(exc), 500)
