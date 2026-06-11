"""
tests/test_ai_processor.py — Testes unitários do adaptador Gemini.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from core.ai_processor import (
    AdaptedContent,
    _build_prompt,
    _parse_response,
    _strip_markdown_fences,
    adapt_content,
)


# ── _strip_markdown_fences ───────────────────────────────────────────────────

class TestStripMarkdownFences:
    def test_remove_json_fence(self):
        raw = "```json\n{\"key\": 1}\n```"
        assert _strip_markdown_fences(raw) == '{"key": 1}'

    def test_remove_plain_fence(self):
        raw = "```\n{\"key\": 1}\n```"
        assert _strip_markdown_fences(raw) == '{"key": 1}'

    def test_no_fence_unchanged(self):
        raw = '{"key": 1}'
        assert _strip_markdown_fences(raw) == '{"key": 1}'

    def test_strips_surrounding_whitespace(self):
        raw = "  \n```json\n{}\n```\n  "
        assert _strip_markdown_fences(raw) == "{}"


# ── _build_prompt ────────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_contains_original_text(self):
        prompt = _build_prompt("Meu conteúdo original", ["twitter"], has_image=False)
        assert "Meu conteúdo original" in prompt

    def test_image_note_when_present(self):
        prompt = _build_prompt("texto", ["instagram"], has_image=True)
        assert "imagem" in prompt.lower()

    def test_no_image_note_when_absent(self):
        prompt = _build_prompt("texto", ["twitter"], has_image=False)
        assert "Acompanha uma imagem" not in prompt

    def test_includes_platform_rules(self):
        prompt = _build_prompt("texto", ["linkedin"], has_image=False)
        assert "LINKEDIN" in prompt
        assert "profissional" in prompt.lower()

    def test_unknown_platform_excluded(self):
        prompt = _build_prompt("texto", ["tiktok"], has_image=False)
        assert "TIKTOK" not in prompt


# ── _parse_response ──────────────────────────────────────────────────────────

class TestParseResponse:
    def _raw(self, data: dict) -> str:
        return json.dumps(data)

    def test_parses_twitter(self):
        raw = self._raw({
            "twitter": {"text": "tweet!", "hashtags": ["tag1"], "is_thread": False, "thread_parts": None}
        })
        result = _parse_response(raw, ["twitter"])
        assert "twitter" in result
        assert result["twitter"].text == "tweet!"
        assert result["twitter"].hashtags == ["tag1"]
        assert result["twitter"].is_thread is False

    def test_parses_thread(self):
        raw = self._raw({
            "twitter": {
                "text": "parte 1",
                "hashtags": [],
                "is_thread": True,
                "thread_parts": ["parte 1", "parte 2"],
            }
        })
        result = _parse_response(raw, ["twitter"])
        assert result["twitter"].is_thread is True
        assert len(result["twitter"].thread_parts) == 2

    def test_parses_instagram_image_description(self):
        raw = self._raw({
            "instagram": {
                "text": "caption",
                "hashtags": ["foto"],
                "image_description": "Foto de paisagem",
            }
        })
        result = _parse_response(raw, ["instagram"])
        assert result["instagram"].image_description == "Foto de paisagem"

    def test_skips_missing_platforms(self):
        raw = self._raw({"twitter": {"text": "t", "hashtags": []}})
        result = _parse_response(raw, ["twitter", "instagram"])
        assert "twitter" in result
        assert "instagram" not in result

    def test_raises_on_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_response("isso não é json", ["twitter"])


# ── AdaptedContent ────────────────────────────────────────────────────────────

class TestAdaptedContent:
    def test_char_count(self):
        c = AdaptedContent(platform="twitter", text="abc de")
        assert c.char_count == 6

    def test_to_dict_keys(self):
        c = AdaptedContent(platform="twitter", text="x", hashtags=["t"])
        d = c.to_dict()
        assert "platform" in d
        assert "text" in d
        assert "hashtags" in d
        assert "char_count" in d
        assert "is_thread" in d


# ── adapt_content (integração com mock) ──────────────────────────────────────

class TestAdaptContent:
    def test_raises_on_empty_text(self):
        with pytest.raises(ValueError, match="vazio"):
            adapt_content("")

    def test_raises_on_invalid_platform(self):
        with pytest.raises(ValueError):
            adapt_content("texto", platforms=["tiktok"])

    def test_returns_adapted_for_all_platforms(self, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory()
        result = adapt_content("Lançamento do nosso novo produto!")
        assert set(result.keys()) == {"twitter", "instagram", "linkedin", "facebook"}

    def test_returns_correct_type(self, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory()
        result = adapt_content("texto qualquer")
        for content in result.values():
            assert isinstance(content, AdaptedContent)

    def test_filters_to_requested_platforms(self, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory(["twitter"])
        result = adapt_content("texto", platforms=["twitter"])
        assert "twitter" in result
        assert "instagram" not in result

    def test_gemini_called_once(self, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory()
        adapt_content("texto")
        mock_gemini.generate_content.assert_called_once()
