import requests
from config import config
from core.ai_processor import AdaptedContent


def post(content: AdaptedContent, image_url: str | None = None) -> dict:
    """
    Publica no LinkedIn via REST API.
    """
    headers = {
        "Authorization": f"Bearer {config.linkedin_access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    text = content.text
    if content.hashtags:
        hashtag_str = " ".join(f"#{h}" for h in content.hashtags)
        text = f"{text}\n\n{hashtag_str}"

    payload: dict = {
        "author": f"urn:li:person:{config.linkedin_person_urn}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    if image_url:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"][
            "shareMediaCategory"
        ] = "IMAGE"
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
            {
                "status": "READY",
                "description": {"text": content.image_description or ""},
                "originalUrl": image_url,
            }
        ]

    response = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json=payload,
    )
    response.raise_for_status()
    post_id = response.json().get("id", "")

    print(f"  ✅ Post publicado no LinkedIn (ID: {post_id})")
    return {"platform": "linkedin", "type": "post", "id": post_id}
