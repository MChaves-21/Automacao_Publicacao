"""core/publishers/pinterest.py — Publisher para PINTEREST."""
import logging
from typing import Optional
from config import config
from core.ai_processor import AdaptedContent

log = logging.getLogger(__name__)

def post(content: AdaptedContent, image_url: Optional[str] = None, **kwargs) -> dict:
    """
    Cria um Pin no Pinterest via API v5.
    Requer: PINTEREST_ACCESS_TOKEN e PINTEREST_BOARD_ID no .env.
    """
    import requests
    if not config.pinterest_access_token:
        raise ValueError("PINTEREST_ACCESS_TOKEN não configurado.")
    if not image_url:
        raise ValueError("Pinterest requer uma imagem para criar um Pin.")

    text = content.text
    if content.hashtags:
        text += "\n" + " ".join(f"#{h}" for h in content.hashtags)

    resp = requests.post(
        "https://api.pinterest.com/v5/pins",
        headers={"Authorization": f"Bearer {config.pinterest_access_token}",
                 "Content-Type": "application/json"},
        json={
            "board_id": config.pinterest_board_id,
            "title": text[:100],
            "description": text,
            "media_source": {"source_type": "image_url", "url": image_url},
            "link": config.app_url or "",
        },
    )
    resp.raise_for_status()
    pin_id = resp.json().get("id", "")
    print(f"  ✅ Pin criado no Pinterest (ID: {pin_id})")
    return {"platform": "pinterest", "id": pin_id}
