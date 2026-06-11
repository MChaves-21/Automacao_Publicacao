"""core/publishers/gmb.py — Publisher para GMB."""
import logging
from typing import Optional
from config import config
from core.ai_processor import AdaptedContent

log = logging.getLogger(__name__)

def post(content: AdaptedContent, image_url: Optional[str] = None, **kwargs) -> dict:
    """
    Cria um post no Google Meu Negócio via My Business API v4.1.
    Requer: GOOGLE_ACCESS_TOKEN e GMB_LOCATION_NAME no .env.
    """
    import requests
    if not config.google_access_token:
        raise ValueError("GOOGLE_ACCESS_TOKEN não configurado.")

    text = content.text[:1500]  # GMB limit
    location = config.gmb_location_name

    body: dict = {
        "languageCode": "pt-BR",
        "summary": text,
        "topicType": "STANDARD",
    }
    if image_url:
        body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": image_url}]

    resp = requests.post(
        f"https://mybusiness.googleapis.com/v4/{location}/localPosts",
        headers={"Authorization": f"Bearer {config.google_access_token}",
                 "Content-Type": "application/json"},
        json=body,
    )
    resp.raise_for_status()
    post_name = resp.json().get("name", "")
    print(f"  ✅ Post criado no Google Meu Negócio ({post_name})")
    return {"platform": "gmb", "id": post_name}
