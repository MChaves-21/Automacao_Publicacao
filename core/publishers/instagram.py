import requests
from config import config
from core.ai_processor import AdaptedContent

GRAPH_URL = "https://graph.facebook.com/v19.0"


def post(content: AdaptedContent, image_url: str | None = None) -> dict:
    """
    Publica no Instagram via Meta Graph API.
    Requer uma imagem para posts no feed.
    """
    account_id = config.instagram_account_id
    access_token = config.instagram_access_token

    caption = content.text
    if content.hashtags:
        hashtag_str = " ".join(f"#{h}" for h in content.hashtags)
        caption = f"{caption}\n\n.\n.\n.\n{hashtag_str}"

    if not image_url:
        print("  ⚠️  Instagram requer imagem. Pulando publicação no feed.")
        print(f"  💡 Sugestão de imagem: {content.image_description or 'não disponível'}")
        return {"platform": "instagram", "status": "skipped", "reason": "no_image"}

    # 1. Criar container de mídia
    container_resp = requests.post(
        f"{GRAPH_URL}/{account_id}/media",
        params={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
    )
    container_resp.raise_for_status()
    container_id = container_resp.json()["id"]

    # 2. Publicar o container
    publish_resp = requests.post(
        f"{GRAPH_URL}/{account_id}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": access_token,
        },
    )
    publish_resp.raise_for_status()
    media_id = publish_resp.json()["id"]

    print(f"  ✅ Post publicado no Instagram (ID: {media_id})")
    return {"platform": "instagram", "type": "post", "id": media_id}
