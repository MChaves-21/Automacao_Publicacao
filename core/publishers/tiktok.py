"""core/publishers/tiktok.py — Publisher para TIKTOK."""
import logging
from typing import Optional
from config import config
from core.ai_processor import AdaptedContent

log = logging.getLogger(__name__)

def post(content: AdaptedContent, image_url: Optional[str] = None, **kwargs) -> dict:
    """
    Publica no TikTok via Content Posting API v2.
    Requer: TIKTOK_ACCESS_TOKEN e TIKTOK_OPEN_ID no .env.
    Suporta vídeos (direto) e texto com imagem (Creator Marketplace API).
    """
    import requests
    if not config.tiktok_access_token:
        raise ValueError("TIKTOK_ACCESS_TOKEN não configurado.")

    text = content.text
    if content.hashtags:
        text += "\n" + " ".join(f"#{h}" for h in content.hashtags)

    # TikTok Content Posting API v2
    resp = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/text/init/",
        headers={
            "Authorization": f"Bearer {config.tiktok_access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title": text[:150],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {"source": "PULL_FROM_URL", "video_url": image_url or ""},
        },
    )
    resp.raise_for_status()
    data = resp.json()
    post_id = data.get("data", {}).get("publish_id", "")
    print(f"  ✅ Publicado no TikTok (ID: {post_id})")
    return {"platform": "tiktok", "id": post_id}
