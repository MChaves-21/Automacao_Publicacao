"""
core/scheduler.py — Agendamento com APScheduler + PostgreSQL (Aiven) ou SQLite local.

Produção (Render + Aiven): define DATABASE_URL no ambiente.
Desenvolvimento local: usa SQLite como fallback automático.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ── Configuração do banco ─────────────────────────────────────────────────────

# Produção → DATABASE_URL do Aiven (postgres://...)
# Local    → SQLite automático
_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///jobs.db")

# Aiven exporta "postgres://" mas SQLAlchemy exige "postgresql://"
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

LOG_FILE = Path(os.getenv("LOG_FILE", "posts_log.json"))

_jobstores  = {"default": SQLAlchemyJobStore(url=_DATABASE_URL)}
_executors  = {"default": ThreadPoolExecutor(max_workers=4)}
_job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}

scheduler = BackgroundScheduler(
    jobstores=_jobstores,
    executors=_executors,
    job_defaults=_job_defaults,
    timezone="America/Sao_Paulo",
)


# ── Log persistente ───────────────────────────────────────────────────────────

def _append_log(entry: dict) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        logging.error("Falha ao escrever no log: %s", exc)


# ── Executor de job ────────────────────────────────────────────────────────────

def _execute_post(
    original_text: str,
    platforms: list[str],
    image_url: Optional[str],
    job_label: str,
) -> None:
    from core.ai_processor import adapt_content
    from core.publishers import PUBLISHERS

    ts = datetime.now()
    print(f"\n⏰ [{ts:%d/%m/%Y %H:%M}] Executando job: {job_label}")

    try:
        adapted = adapt_content(original_text, image_url=image_url, platforms=platforms)
    except Exception as exc:
        _append_log({
            "timestamp": ts.isoformat(),
            "label": job_label,
            "platforms": platforms,
            "results": [],
            "errors": [],
            "fatal_error": str(exc),
        })
        print(f"  ❌ Erro ao adaptar conteúdo: {exc}")
        return

    results, errors = [], []
    for platform in platforms:
        if platform not in adapted:
            continue
        publisher = PUBLISHERS.get(platform)
        if not publisher:
            logging.warning("Publisher não encontrado para '%s'", platform)
            continue
        print(f"  📤 {platform.upper()}...")
        try:
            results.append(publisher(adapted[platform], image_url=image_url))
        except Exception as exc:
            errors.append({"platform": platform, "error": str(exc)})
            print(f"  ❌ {platform}: {exc}")

    _append_log({
        "timestamp": ts.isoformat(),
        "label": job_label,
        "platforms": platforms,
        "results": results,
        "errors": errors,
        "fatal_error": None,
    })
    print(f"  ✅ Concluído — {len(results)} ok, {len(errors)} erro(s)")


# ── API pública ────────────────────────────────────────────────────────────────

def ensure_started() -> None:
    if not scheduler.running:
        scheduler.start()


def schedule_post(
    original_text: str,
    run_at: datetime,
    platforms: Optional[list[str]] = None,
    image_url: Optional[str] = None,
    label: Optional[str] = None,
) -> str:
    if run_at <= datetime.now(tz=run_at.tzinfo):
        raise ValueError("run_at deve ser uma data futura.")

    if platforms is None:
        platforms = ["twitter", "instagram", "linkedin", "facebook"]
    if label is None:
        label = f"post_{run_at:%Y%m%d_%H%M}"

    ensure_started()

    job = scheduler.add_job(
        func=_execute_post,
        trigger="date",
        run_date=run_at,
        kwargs={
            "original_text": original_text,
            "platforms": platforms,
            "image_url": image_url,
            "job_label": label,
        },
        id=label,
        name=label,
        replace_existing=True,
    )
    return job.id


def list_jobs() -> list[dict]:
    ensure_started()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.strftime("%d/%m/%Y %H:%M")
            if job.next_run_time else "—",
            "platforms": job.kwargs.get("platforms", []),
        }
        for job in scheduler.get_jobs()
    ]


def cancel_job(job_id: str) -> bool:
    ensure_started()
    try:
        scheduler.remove_job(job_id)
        return True
    except Exception:
        return False


def read_log(limit: int = 50) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    with LOG_FILE.open("r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    return list(reversed(entries[-limit:]))
