"""core/webhooks.py — Disparo de webhooks e notificações Slack."""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any

import requests

from config import config

log = logging.getLogger(__name__)

# ── Slack ─────────────────────────────────────────────────────────────────────

SLACK_ICONS = {
    "post.published": ":rocket:",
    "post.approved":  ":white_check_mark:",
    "post.rejected":  ":x:",
    "post.failed":    ":warning:",
    "post.pending":   ":clipboard:",
}


def notify_slack(event: str, message: str, details: dict | None = None) -> bool:
    """Envia notificação para o Slack via Incoming Webhook."""
    if not config.slack_webhook_url:
        return False

    icon  = SLACK_ICONS.get(event, ":bell:")
    plats = ", ".join(details.get("platforms", [])) if details else ""
    author = details.get("author", "") if details else ""

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"{icon} *{message}*"}},
    ]
    if plats:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"Plataformas: {plats}  |  Por: {author}"}
        ]})

    try:
        resp = requests.post(
            config.slack_webhook_url,
            json={"blocks": blocks},
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as exc:
        log.error("Falha ao notificar Slack: %s", exc)
        return False


# ── Webhooks HTTP ─────────────────────────────────────────────────────────────

def _sign_payload(secret: str, payload: bytes) -> str:
    """Gera assinatura HMAC-SHA256 para o payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def dispatch_event(event: str, data: dict) -> list[dict]:
    """
    Dispara um evento para todos os webhooks cadastrados que escutam esse evento.
    Retorna lista de resultados por webhook.
    """
    try:
        from core.models import Webhook, db
        hooks = Webhook.query.filter_by(is_active=True).all()
    except Exception as exc:
        log.error("Erro ao buscar webhooks: %s", exc)
        return []

    results = []
    payload = json.dumps({
        "event":     event,
        "timestamp": int(time.time()),
        "data":      data,
    }).encode()

    for hook in hooks:
        events = hook.events or []
        if event not in events and "*" not in events:
            continue

        headers = {
            "Content-Type":           "application/json",
            "X-MktAuto-Event":        event,
            "X-MktAuto-Delivery":     str(int(time.time())),
        }
        if hook.secret:
            headers["X-MktAuto-Signature"] = _sign_payload(hook.secret, payload)

        try:
            resp = requests.post(hook.url, data=payload, headers=headers, timeout=8)
            status = resp.status_code
            log.info("Webhook '%s' → %s: %d", hook.name, event, status)
        except Exception as exc:
            status = 0
            log.warning("Webhook '%s' falhou: %s", hook.name, exc)

        hook.last_triggered = datetime.utcnow()
        hook.last_status    = status
        results.append({"webhook": hook.name, "status": status})

    try:
        from core.models import db
        db.session.commit()
    except Exception:
        pass

    return results


def fire(event: str, post=None, extra: dict | None = None) -> None:
    """
    Atalho para disparar evento de post com dados padronizados.
    Combina webhook HTTP + Slack em um único call.
    """
    data: dict[str, Any] = extra or {}

    if post:
        data.update({
            "post_id":   post.id,
            "content":   (post.content or "")[:200],
            "platforms": post.platforms or [],
            "status":    post.status,
            "author":    post.author.username if post.author else "sistema",
        })

    # Slack
    messages = {
        "post.published": f"Post publicado em {', '.join(data.get('platforms', []))}",
        "post.approved":  f"Post aprovado por {data.get('reviewer', 'revisor')}",
        "post.rejected":  "Post devolvido para edição",
        "post.failed":    f"Falha ao publicar em {data.get('failed_platform', 'plataforma')}",
        "post.pending":   f"Post de '{data.get('author', '?')}' aguarda aprovação",
    }
    msg = messages.get(event, event)
    notify_slack(event, msg, data)

    # Webhooks HTTP (em background para não bloquear o request)
    try:
        dispatch_event(event, data)
    except Exception as exc:
        log.error("Erro ao disparar webhooks: %s", exc)
