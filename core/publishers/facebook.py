import requests
from config import config
from core.ai_processor import AdaptedContent

GRAPH_URL = "https://graph.facebook.com/v19.0"


def post(content: AdaptedContent, image_url: str | None = None) -> dict:
    """
    Publica em uma página do Facebook via Meta Graph API.
    """
    page_id = config.facebook_page_id
    access_token = config.facebook_access_token

    message = content.text
    if content.hashtags:
        hashtag_str = " ".join(f"#{h}" for h in content.hashtags)
        message = f"{message}\n\n{hashtag_str}"

    if image_url:
        endpoint = f"{GRAPH_URL}/{page_id}/photos"
        payload = {
            "url": image_url,
            "message": message,
            "access_token": access_token,
        }
    else:
        endpoint = f"{GRAPH_URL}/{page_id}/feed"
        payload = {
            "message": message,
            "access_token": access_token,
        }

    response = requests.post(endpoint, data=payload)
    response.raise_for_status()
    post_id = response.json().get("post_id") or response.json().get("id", "")

    print(f"  ✅ Post publicado no Facebook (ID: {post_id})")
    return {"platform": "facebook", "type": "post", "id": post_id}
