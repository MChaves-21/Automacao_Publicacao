"""core/publishers/whatsapp.py — Publisher para WHATSAPP."""
import logging
from typing import Optional
from config import config
from core.ai_processor import AdaptedContent

log = logging.getLogger(__name__)

def post(content: AdaptedContent, image_url: Optional[str] = None, **kwargs) -> dict:
    """
    Envia mensagem via WhatsApp Business Cloud API (Meta).
    Requer: WHATSAPP_TOKEN, WHATSAPP_PHONE_ID e WHATSAPP_RECIPIENT no .env.
    """
    import requests
    if not config.whatsapp_token:
        raise ValueError("WHATSAPP_TOKEN não configurado.")

    text = content.text
    if content.hashtags:
        text += "\n" + " ".join(f"#{h}" for h in content.hashtags)

    phone_id = config.whatsapp_phone_id
    payload: dict = {
        "messaging_product": "whatsapp",
        "to": config.whatsapp_recipient,
    }

    if image_url:
        payload.update({"type": "image", "image": {"link": image_url, "caption": text}})
    else:
        payload.update({"type": "text", "text": {"body": text}})

    resp = requests.post(
        f"https://graph.facebook.com/v19.0/{phone_id}/messages",
        headers={"Authorization": f"Bearer {config.whatsapp_token}",
                 "Content-Type": "application/json"},
        json=payload,
    )
    resp.raise_for_status()
    msg_id = resp.json().get("messages", [{}])[0].get("id", "")
    print(f"  ✅ Mensagem enviada no WhatsApp (ID: {msg_id})")
    return {"platform": "whatsapp", "id": msg_id}
