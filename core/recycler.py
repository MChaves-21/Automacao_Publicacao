"""core/recycler.py — Reciclagem de conteúdo: repostar top posts com variações Gemini."""
import logging
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)


def find_recyclable(limit: int = 10, min_age_days: int = 30) -> list[dict]:
    """
    Retorna posts publicados há mais de `min_age_days` dias,
    ordenados por número de plataformas publicadas (proxy de sucesso).
    """
    from core.models import Post, PostStatus

    cutoff = datetime.utcnow() - timedelta(days=min_age_days)
    posts  = (
        Post.query
        .filter(Post.status == PostStatus.PUBLISHED)
        .filter(Post.published_at <= cutoff)
        .order_by(Post.published_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id":          p.id,
            "content":     p.content,
            "platforms":   p.platforms or [],
            "published_at":p.published_at.isoformat() if p.published_at else None,
            "results":     p.results or {},
        }
        for p in posts
    ]


def recycle_post(post_id: int, variation: bool = True,
                 run_at: Optional[datetime] = None) -> dict:
    """
    Recicla um post publicado:
      - Se variation=True, gera uma variação do texto com Gemini
      - Agenda ou cria como rascunho para revisão
    Retorna o novo post criado.
    """
    from core.models import Post, PostStatus, db
    from core.ai_processor import adapt_content

    from flask import abort
    original = Post.query.get(post_id)
    if not original:
        abort(404)
    new_content = original.content

    if variation:
        new_content = _generate_variation(original.content)

    try:
        adapted = adapt_content(new_content, platforms=original.platforms)
    except Exception as exc:
        log.error("Erro ao adaptar conteúdo reciclado: %s", exc)
        adapted = {}

    new_post = Post(
        author_id=original.author_id,
        content=new_content,
        image_url=original.image_url,
        platforms=original.platforms,
        adapted_content={p: c.to_dict() for p, c in adapted.items()},
        status=PostStatus.DRAFT,
        scheduled_at=run_at,
    )
    db.session.add(new_post)
    db.session.commit()

    log.info("Post %d reciclado → novo post %d", post_id, new_post.id)
    return new_post.to_dict()


def _generate_variation(original_text: str) -> str:
    """Usa Gemini para gerar uma variação do texto original."""
    import re
    import google.generativeai as genai
    from config import config

    genai.configure(api_key=config.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    resp = model.generate_content(
        f"Reescreva o post abaixo de forma diferente, mantendo a mensagem central "
        f"mas com outras palavras, estrutura e ângulo. "
        f"Responda APENAS com o novo texto, sem explicações.\n\n"
        f"Post original:\n{original_text}"
    )
    return resp.text.strip()
