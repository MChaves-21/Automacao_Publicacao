"""routes/api_tools.py — Ferramentas: imagem, CSV, sentimento, melhor horário, templates, 2FA, users."""
import csv
import io
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

tools_bp = Blueprint("tools", __name__, url_prefix="/api")


def _bad(msg, code=400): return jsonify({"error": msg}), code


# ── Templates ─────────────────────────────────────────────────────────────────

@tools_bp.get("/templates")
@login_required
def list_templates():
    from core.models import Template
    ts = Template.query.order_by(Template.created_at.desc()).all()
    return jsonify([t.to_dict() for t in ts])


@tools_bp.post("/templates")
@login_required
def create_template():
    from core.models import Template, db
    from core.audit import log_action
    data = request.get_json(silent=True) or {}
    name    = (data.get("name") or "").strip()
    content = (data.get("content") or "").strip()
    if not name or not content:
        return _bad("Nome e conteúdo são obrigatórios.")
    t = Template(name=name, description=data.get("description"),
                 content=content, platforms=data.get("platforms"),
                 category=data.get("category"), author_id=current_user.id)
    db.session.add(t); db.session.commit()
    log_action("create_template", "template", t.id, {"name": name})
    return jsonify(t.to_dict()), 201


@tools_bp.delete("/templates/<int:tid>")
@login_required
def delete_template(tid: int):
    from core.models import Template, db
    from core.audit import log_action
    t = Template.query.get_or_404(tid)
    if t.author_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Permissão negada."}), 403
    db.session.delete(t); db.session.commit()
    log_action("delete_template", "template", tid)
    return jsonify({"ok": True})


# ── Geração de imagem DALL-E 3 ────────────────────────────────────────────────

@tools_bp.post("/image/generate")
@login_required
def generate_image():
    from core.image_gen import generate_image as gen, suggest_image_prompt
    from core.audit import log_action
    data    = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    prompt  = (data.get("prompt") or "").strip()
    size    = data.get("size", "1024x1024")
    if not content and not prompt:
        return _bad("Forneça o conteúdo do post ou um prompt de imagem.")
    try:
        if not prompt:
            prompt = suggest_image_prompt(content)
        url = gen(prompt, size=size)
        log_action("generate_image", details={"prompt": prompt[:100]})
        return jsonify({"url": url, "prompt": prompt})
    except Exception as exc:
        return _bad(str(exc), 500)


# ── CSV bulk scheduling ───────────────────────────────────────────────────────

@tools_bp.post("/posts/import-csv")
@login_required
def import_csv():
    """
    Importa posts em massa via CSV.
    Colunas: content, platforms (separadas por |), scheduled_at (YYYY-MM-DDTHH:MM), image_url
    """
    from core.models import Post, PostStatus, db
    from core.audit import log_action

    if "file" not in request.files:
        return _bad("Envie o arquivo como campo 'file' (multipart/form-data).")

    file = request.files["file"]
    content_str = file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content_str))

    created, errors = [], []
    for i, row in enumerate(reader, 1):
        content = (row.get("content") or "").strip()
        if not content:
            errors.append({"row": i, "error": "Coluna 'content' vazia"}); continue

        platforms = [p.strip() for p in (row.get("platforms") or "twitter").split("|") if p.strip()]
        image_url = (row.get("image_url") or "").strip() or None
        run_at    = None
        raw_dt    = (row.get("scheduled_at") or "").strip()
        if raw_dt:
            try: run_at = datetime.strptime(raw_dt, "%Y-%m-%dT%H:%M")
            except ValueError: errors.append({"row": i, "error": f"Data inválida: {raw_dt}"}); continue

        status = PostStatus.APPROVED if current_user.can_publish_direct else PostStatus.PENDING
        post = Post(author_id=current_user.id, content=content, platforms=platforms,
                    image_url=image_url, status=status, scheduled_at=run_at)
        db.session.add(post)
        created.append(i)

    db.session.commit()
    log_action("import_csv", details={"created": len(created), "errors": len(errors)})
    return jsonify({"created": len(created), "errors": errors})


# ── Melhor horário ────────────────────────────────────────────────────────────

@tools_bp.get("/best-time/<platform>")
@login_required
def best_time(platform: str):
    from core.audit import suggest_best_time
    from core.scheduler import read_log
    entries = read_log(limit=200)
    suggestion = suggest_best_time(platform, entries)
    return jsonify(suggestion)


# ── Análise de sentimento ─────────────────────────────────────────────────────

@tools_bp.post("/sentiment")
@login_required
def sentiment():
    from core.audit import analyze_sentiment
    data     = request.get_json(silent=True) or {}
    comments = data.get("comments", [])
    if not comments:
        return _bad("Envie uma lista de comentários em 'comments'.")
    try:
        result = analyze_sentiment(comments)
        return jsonify(result)
    except Exception as exc:
        return _bad(str(exc), 500)


# ── A/B Testing ───────────────────────────────────────────────────────────────

@tools_bp.post("/ab-test")
@login_required
def ab_test():
    from core.audit import generate_ab_variants
    data      = request.get_json(silent=True) or {}
    content   = (data.get("content") or "").strip()
    platforms = data.get("platforms") or ["twitter", "linkedin"]
    if not content:
        return _bad("Conteúdo obrigatório.")
    try:
        adapted_a, adapted_b = generate_ab_variants(content, platforms)
        return jsonify({
            "a": {p: c.to_dict() for p, c in adapted_a.items()},
            "b": {p: c.to_dict() for p, c in adapted_b.items()},
        })
    except Exception as exc:
        return _bad(str(exc), 500)


# ── Log de auditoria ──────────────────────────────────────────────────────────

@tools_bp.get("/audit")
@login_required
def audit_log():
    if not current_user.is_admin:
        return jsonify({"error": "Apenas admins."}), 403
    from core.models import AuditLog
    page  = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    logs  = (AuditLog.query.order_by(AuditLog.created_at.desc())
             .offset((page - 1) * limit).limit(limit).all())
    return jsonify([l.to_dict() for l in logs])


# ── Gerenciamento de usuários (admin) ─────────────────────────────────────────

@tools_bp.get("/users")
@login_required
def list_users():
    if not current_user.is_admin:
        return jsonify({"error": "Apenas admins."}), 403
    from core.models import User
    users = User.query.order_by(User.created_at).all()
    return jsonify([u.to_dict() for u in users])


@tools_bp.patch("/users/<int:uid>")
@login_required
def update_user(uid: int):
    if not current_user.is_admin:
        return jsonify({"error": "Apenas admins."}), 403
    from core.models import User, db
    from core.audit import log_action
    user = User.query.get_or_404(uid)
    data = request.get_json(silent=True) or {}
    if "role" in data and data["role"] in ("admin", "revisor", "editor"):
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    db.session.commit()
    log_action("update_user", "user", uid, {"role": user.role})
    return jsonify(user.to_dict())


# ── 2FA (TOTP) ────────────────────────────────────────────────────────────────

@tools_bp.post("/2fa/setup")
@login_required
def setup_2fa():
    import pyotp, qrcode, base64
    from io import BytesIO
    from core.models import db

    secret = pyotp.random_base32()
    current_user.otp_secret = secret
    db.session.commit()

    totp = pyotp.TOTP(secret)
    uri  = totp.provisioning_uri(current_user.email, issuer_name="MktAutomation")

    img = qrcode.make(uri)
    buf = BytesIO(); img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({"secret": secret, "uri": uri, "qr_image": f"data:image/png;base64,{qr_b64}"})


@tools_bp.post("/2fa/verify")
@login_required
def verify_2fa():
    import pyotp
    from core.models import db
    data  = request.get_json(silent=True) or {}
    token = data.get("token", "")
    if not current_user.otp_secret:
        return _bad("Configure o 2FA primeiro.")
    totp = pyotp.TOTP(current_user.otp_secret)
    if totp.verify(token):
        current_user.otp_enabled = True
        db.session.commit()
        return jsonify({"ok": True, "message": "2FA ativado com sucesso!"})
    return _bad("Código inválido. Tente novamente.", 401)


@tools_bp.post("/2fa/disable")
@login_required
def disable_2fa():
    from core.models import db
    current_user.otp_enabled = False
    current_user.otp_secret  = None
    db.session.commit()
    return jsonify({"ok": True})


# ── Estatísticas de engajamento (estrutura real + mock) ───────────────────────

@tools_bp.get("/engagement/<platform>/<post_ref>")
@login_required
def engagement(platform: str, post_ref: str):
    """
    Retorna métricas de engajamento de um post.
    Para usar com dados reais, configure os tokens de cada plataforma.
    """
    import random
    # Estrutura pronta para integração real — atualmente retorna dados simulados
    base = random.randint(100, 5000)
    return jsonify({
        "platform": platform,
        "post_ref": post_ref,
        "metrics": {
            "impressions": base * random.randint(5, 20),
            "reach":       base * random.randint(3, 10),
            "likes":       base,
            "comments":    base // random.randint(5, 20),
            "shares":      base // random.randint(10, 30),
            "clicks":      base // random.randint(2, 8),
        },
        "note": "Conecte as APIs de cada plataforma para dados reais."
    })
