"""core/rss_monitor.py — Monitoramento de feeds RSS e criação automática de posts."""
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


def check_feed(feed_id: int) -> list[dict]:
    """
    Verifica um feed RSS por novos itens e cria posts automaticamente.
    Retorna lista de posts criados.
    """
    import feedparser
    from core.models import RssFeed, Post, PostStatus, db
    from core.ai_processor import adapt_content

    feed = RssFeed.query.get(feed_id)
    if not feed or not feed.is_active:
        return []

    log.info("Verificando feed RSS: %s", feed.name)

    try:
        parsed = feedparser.parse(feed.url)
    except Exception as exc:
        log.error("Erro ao parsear feed %s: %s", feed.url, exc)
        return []

    entries = parsed.entries or []
    if not entries:
        return []

    # Identificar novos itens (após o último verificado)
    new_entries = []
    for entry in entries[:10]:  # máximo 10 por verificação
        entry_id = entry.get("id") or entry.get("link", "")
        if entry_id == feed.last_entry_id:
            break
        new_entries.append(entry)

    created_posts = []

    for entry in reversed(new_entries):  # mais antigo primeiro
        title   = entry.get("title", "")
        summary = entry.get("summary", "")
        link    = entry.get("link", "")
        content = f"{title}\n\n{summary[:500]}\n\n🔗 {link}".strip()

        try:
            adapted = adapt_content(content, platforms=feed.platforms or ["twitter", "linkedin"])

            post = Post(
                author_id=feed.author_id,
                content=content,
                platforms=feed.platforms or ["twitter", "linkedin"],
                adapted_content={p: c.to_dict() for p, c in adapted.items()},
                status=PostStatus.DRAFT,
            )
            db.session.add(post)
            created_posts.append({"title": title, "link": link})
            log.info("Post criado via RSS: %s", title[:60])
        except Exception as exc:
            log.error("Erro ao criar post do RSS '%s': %s", title, exc)

    # Atualizar controle do feed
    if new_entries:
        feed.last_entry_id = (
            new_entries[0].get("id") or new_entries[0].get("link", "")
        )
    feed.last_checked = datetime.utcnow()
    db.session.commit()

    return created_posts


def register_rss_jobs(scheduler, app) -> None:
    """
    Registra um job no APScheduler para cada feed RSS ativo.
    Deve ser chamado na inicialização do servidor.
    """
    with app.app_context():
        from core.models import RssFeed

        feeds = RssFeed.query.filter_by(is_active=True).all()
        for feed in feeds:
            _schedule_feed(scheduler, app, feed)

        if feeds:
            log.info("Registrados %d feed(s) RSS no scheduler.", len(feeds))


def _schedule_feed(scheduler, app, feed) -> None:
    """Agenda a verificação periódica de um feed."""
    job_id = f"rss_feed_{feed.id}"

    def run():
        with app.app_context():
            check_feed(feed.id)

    scheduler.add_job(
        func=run,
        trigger="interval",
        hours=feed.interval_hours or 6,
        id=job_id,
        name=f"RSS: {feed.name}",
        replace_existing=True,
    )


def refresh_rss_schedule(scheduler, app, feed_id: int) -> None:
    """Reagenda um feed específico (após criar ou editar)."""
    with app.app_context():
        from core.models import RssFeed
        feed = RssFeed.query.get(feed_id)
        if feed and feed.is_active:
            _schedule_feed(scheduler, app, feed)
        else:
            try:
                scheduler.remove_job(f"rss_feed_{feed_id}")
            except Exception:
                pass
