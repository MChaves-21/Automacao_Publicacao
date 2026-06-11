"""routes/api.py — Endpoints gerais: stats, jobs, preview, publish, log, me."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

api_bp = Blueprint("api", __name__, url_prefix="/api")

def _bad(msg, code=400): return jsonify({"error": msg}), code
def _get_platforms(data): return data.get("platforms") or ["twitter","instagram","linkedin","facebook"]

@api_bp.get("/me")
@login_required
def get_me():
    return jsonify(current_user.to_dict())

@api_bp.get("/jobs")
@login_required
def get_jobs():
    from core.scheduler import list_jobs
    return jsonify(list_jobs())

@api_bp.post("/jobs")
@login_required
def create_job():
    from core.scheduler import schedule_post
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    run_at_str = data.get("run_at", "")
    if not text: return _bad("O campo 'text' é obrigatório.")
    if not run_at_str: return _bad("O campo 'run_at' é obrigatório.")
    try: run_at = datetime.strptime(run_at_str, "%Y-%m-%dT%H:%M")
    except ValueError: return _bad("Formato de data inválido. Use YYYY-MM-DDTHH:MM.")
    try:
        job_id = schedule_post(original_text=text, run_at=run_at,
                               platforms=_get_platforms(data),
                               image_url=data.get("image_url") or None,
                               label=(data.get("label") or "").strip() or None)
    except ValueError as exc: return _bad(str(exc))
    return jsonify({"id": job_id, "run_at": run_at.strftime("%d/%m/%Y %H:%M")}), 201

@api_bp.delete("/jobs/<job_id>")
@login_required
def delete_job(job_id):
    from core.scheduler import cancel_job
    if cancel_job(job_id): return jsonify({"ok": True})
    return _bad("Job não encontrado.", 404)

@api_bp.post("/publish")
@login_required
def publish_now():
    from core.ai_processor import adapt_content
    from core.publishers import PUBLISHERS
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text: return _bad("O campo 'text' é obrigatório.")
    platforms = _get_platforms(data)
    image_url = data.get("image_url") or None
    try: adapted = adapt_content(text, image_url=image_url, platforms=platforms)
    except Exception as exc: return _bad(str(exc), 500)
    results, errors = [], []
    for p in platforms:
        pub = PUBLISHERS.get(p)
        if not pub: continue
        try: results.append(pub(adapted[p], image_url=image_url))
        except Exception as exc: errors.append({"platform": p, "error": str(exc)})
    return jsonify({"results": results, "errors": errors})

@api_bp.post("/preview")
@login_required
def preview():
    from core.ai_processor import adapt_content
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text: return _bad("O campo 'text' é obrigatório.")
    try:
        adapted = adapt_content(text, image_url=data.get("image_url") or None,
                                platforms=_get_platforms(data))
    except Exception as exc: return _bad(str(exc), 500)
    return jsonify({p: c.to_dict() for p, c in adapted.items()})

@api_bp.get("/log")
@login_required
def get_log():
    from core.scheduler import read_log
    return jsonify(read_log())

@api_bp.get("/stats")
@login_required
def get_stats():
    from core.scheduler import list_jobs, read_log
    from core.models import Post, PostStatus
    jobs    = list_jobs()
    entries = read_log(limit=500)
    published = sum(len(e.get("results", [])) for e in entries)
    errors    = sum(len(e.get("errors",   [])) for e in entries)
    by_platform: dict[str, int] = {}
    for e in entries:
        for r in e.get("results", []):
            p = r.get("platform", "")
            by_platform[p] = by_platform.get(p, 0) + 1
    try:
        pending_count = Post.query.filter_by(status=PostStatus.PENDING).count()
    except Exception:
        pending_count = 0
    return jsonify({
        "scheduled":   len(jobs),
        "published":   published,
        "errors":      errors,
        "sessions":    len(entries),
        "pending":     pending_count,
        "by_platform": by_platform,
        "next_job":    jobs[0] if jobs else None,
    })
