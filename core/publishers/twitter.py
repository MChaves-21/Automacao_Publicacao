import tweepy
from config import config
from core.ai_processor import AdaptedContent


def get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=config.twitter_bearer_token,
        consumer_key=config.twitter_api_key,
        consumer_secret=config.twitter_api_secret,
        access_token=config.twitter_access_token,
        access_token_secret=config.twitter_access_secret,
    )


def post(content: AdaptedContent, image_url: str | None = None) -> dict:
    """
    Publica no Twitter. Suporta tweets simples e threads.
    """
    client = get_client()
    posted = []

    if content.is_thread and content.thread_parts:
        print(f"  🧵 Publicando thread com {len(content.thread_parts)} partes...")
        previous_id = None
        for i, part in enumerate(content.thread_parts):
            text = part
            # Adiciona hashtags apenas no último tweet da thread
            if i == len(content.thread_parts) - 1 and content.hashtags:
                hashtag_str = " ".join(f"#{h}" for h in content.hashtags)
                text = f"{text}\n\n{hashtag_str}"

            kwargs: dict = {"text": text}
            if previous_id:
                kwargs["in_reply_to_tweet_id"] = previous_id

            response = client.create_tweet(**kwargs)
            previous_id = response.data["id"]
            posted.append(response.data["id"])
            print(f"    ✅ Parte {i+1} postada (ID: {previous_id})")

        return {"platform": "twitter", "type": "thread", "tweet_ids": posted}

    else:
        text = content.text
        if content.hashtags:
            hashtag_str = " ".join(f"#{h}" for h in content.hashtags)
            full_text = f"{text}\n\n{hashtag_str}"
            if len(full_text) <= 280:
                text = full_text

        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        print(f"  ✅ Tweet publicado (ID: {tweet_id})")
        return {"platform": "twitter", "type": "tweet", "id": tweet_id}
