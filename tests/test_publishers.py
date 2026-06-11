"""
tests/test_publishers.py — Testes unitários dos publishers com mocks HTTP.
"""
from unittest.mock import MagicMock, patch

import pytest

from core.ai_processor import AdaptedContent


def make_content(platform: str, **kwargs) -> AdaptedContent:
    defaults = {
        "platform": platform,
        "text": f"Texto de teste para {platform}",
        "hashtags": ["marketing", "digital"],
    }
    defaults.update(kwargs)
    return AdaptedContent(**defaults)


# ── Twitter ───────────────────────────────────────────────────────────────────

class TestTwitterPublisher:
    def test_posts_simple_tweet(self):
        from core.publishers.twitter import post

        mock_client = MagicMock()
        mock_client.create_tweet.return_value.data = {"id": "tweet-123"}

        with patch("core.publishers.twitter.get_client", return_value=mock_client):
            result = post(make_content("twitter"))

        mock_client.create_tweet.assert_called_once()
        assert result["platform"] == "twitter"
        assert result["id"] == "tweet-123"

    def test_appends_hashtags_to_tweet(self):
        from core.publishers.twitter import post

        mock_client = MagicMock()
        mock_client.create_tweet.return_value.data = {"id": "1"}

        content = make_content("twitter", text="Texto curto", hashtags=["tag1", "tag2"])
        with patch("core.publishers.twitter.get_client", return_value=mock_client):
            post(content)

        call_kwargs = mock_client.create_tweet.call_args
        text_sent = call_kwargs[1].get("text") or call_kwargs[0][0]
        assert "#tag1" in text_sent

    def test_posts_thread_when_is_thread(self):
        from core.publishers.twitter import post

        mock_client = MagicMock()
        mock_client.create_tweet.return_value.data = {"id": "999"}

        content = make_content(
            "twitter",
            is_thread=True,
            thread_parts=["Parte 1 da thread", "Parte 2 da thread"],
        )
        with patch("core.publishers.twitter.get_client", return_value=mock_client):
            result = post(content)

        assert mock_client.create_tweet.call_count == 2
        assert result["type"] == "thread"
        assert len(result["tweet_ids"]) == 2

    def test_second_tweet_replies_to_first(self):
        from core.publishers.twitter import post

        ids = iter(["id-1", "id-2"])
        mock_client = MagicMock()
        mock_client.create_tweet.side_effect = [
            MagicMock(data={"id": "id-1"}),
            MagicMock(data={"id": "id-2"}),
        ]

        content = make_content("twitter", is_thread=True, thread_parts=["p1", "p2"])
        with patch("core.publishers.twitter.get_client", return_value=mock_client):
            post(content)

        second_call = mock_client.create_tweet.call_args_list[1]
        assert second_call[1].get("in_reply_to_tweet_id") == "id-1"


# ── Instagram ─────────────────────────────────────────────────────────────────

class TestInstagramPublisher:
    def test_skips_without_image(self):
        from core.publishers.instagram import post

        result = post(make_content("instagram"), image_url=None)
        assert result["status"] == "skipped"
        assert result["reason"] == "no_image"

    def test_posts_with_image(self):
        from core.publishers.instagram import post

        mock_resp_container = MagicMock()
        mock_resp_container.json.return_value = {"id": "container-1"}
        mock_resp_container.raise_for_status = MagicMock()

        mock_resp_publish = MagicMock()
        mock_resp_publish.json.return_value = {"id": "media-abc"}
        mock_resp_publish.raise_for_status = MagicMock()

        with patch("core.publishers.instagram.requests.post") as mock_post:
            mock_post.side_effect = [mock_resp_container, mock_resp_publish]
            result = post(make_content("instagram"), image_url="https://img.com/foto.jpg")

        assert result["platform"] == "instagram"
        assert result["id"] == "media-abc"
        assert mock_post.call_count == 2

    def test_includes_hashtags_in_caption(self):
        from core.publishers.instagram import post

        content = make_content("instagram", hashtags=["hashtest"])
        calls_made = []

        def capture_post(url, params):
            calls_made.append(params)
            resp = MagicMock()
            resp.json.return_value = {"id": "x"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("core.publishers.instagram.requests.post", side_effect=capture_post):
            post(content, image_url="https://img.com/x.jpg")

        first_call_params = calls_made[0]
        assert "#hashtest" in first_call_params.get("caption", "")


# ── LinkedIn ──────────────────────────────────────────────────────────────────

class TestLinkedInPublisher:
    def test_posts_successfully(self):
        from core.publishers.linkedin import post

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "urn:li:ugcPost:123"}
        mock_resp.raise_for_status = MagicMock()

        with patch("core.publishers.linkedin.requests.post", return_value=mock_resp):
            result = post(make_content("linkedin"))

        assert result["platform"] == "linkedin"

    def test_sends_correct_author_urn(self):
        from core.publishers.linkedin import post
        from config import config

        captured = {}
        def capture(url, headers, json):
            captured["body"] = json
            resp = MagicMock()
            resp.json.return_value = {"id": "x"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("core.publishers.linkedin.requests.post", side_effect=capture):
            post(make_content("linkedin"))

        author = captured["body"]["author"]
        assert "urn:li:person:" in author

    def test_uses_image_media_category_when_image(self):
        from core.publishers.linkedin import post

        captured = {}
        def capture(url, headers, json):
            captured["body"] = json
            resp = MagicMock()
            resp.json.return_value = {"id": "x"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("core.publishers.linkedin.requests.post", side_effect=capture):
            post(make_content("linkedin"), image_url="https://img.com/img.jpg")

        share = captured["body"]["specificContent"]["com.linkedin.ugc.ShareContent"]
        assert share["shareMediaCategory"] == "IMAGE"


# ── Facebook ──────────────────────────────────────────────────────────────────

class TestFacebookPublisher:
    def test_posts_text_only(self):
        from core.publishers.facebook import post

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "page_post_123"}
        mock_resp.raise_for_status = MagicMock()

        with patch("core.publishers.facebook.requests.post", return_value=mock_resp) as mock_req:
            result = post(make_content("facebook"))

        assert result["platform"] == "facebook"
        # Sem imagem → usa endpoint /feed
        assert "/feed" in mock_req.call_args[0][0]

    def test_posts_with_image_uses_photos_endpoint(self):
        from core.publishers.facebook import post

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"post_id": "photo_post_456"}
        mock_resp.raise_for_status = MagicMock()

        with patch("core.publishers.facebook.requests.post", return_value=mock_resp) as mock_req:
            post(make_content("facebook"), image_url="https://img.com/photo.jpg")

        assert "/photos" in mock_req.call_args[0][0]

    def test_includes_hashtags_in_message(self):
        from core.publishers.facebook import post

        content = make_content("facebook", hashtags=["fbtest"])
        captured_data = {}

        def capture(url, data):
            captured_data.update(data)
            resp = MagicMock()
            resp.json.return_value = {"id": "x"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("core.publishers.facebook.requests.post", side_effect=capture):
            post(content)

        assert "#fbtest" in captured_data.get("message", "")
