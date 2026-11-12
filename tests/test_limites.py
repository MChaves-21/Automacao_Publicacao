"""
tests/test_limites.py — Validação do tamanho dos textos e nova geração pelo Gemini.
"""
import json
from unittest.mock import MagicMock

from core.ai_processor import (
    AdaptedContent,
    MAX_TENTATIVAS_REESCRITA,
    TWEET_MAX,
    adapt_content,
    ensure_within_limits,
    final_length,
    find_violations,
)


def _resp(data: dict) -> MagicMock:
    r = MagicMock()
    r.text = json.dumps(data)
    return r


def _tweet(text, hashtags=None, **kw):
    return AdaptedContent(platform="twitter", text=text, hashtags=hashtags or [], **kw)


class TestFinalLength:
    def test_sem_hashtags(self):
        assert final_length("abc", []) == 3

    def test_conta_linha_em_branco_e_hashtags(self):
        # "abc" + "\n\n" + "#a #b"
        assert final_length("abc", ["a", "b"]) == 3 + 2 + 5


class TestFindViolations:
    def test_texto_dentro_do_limite(self):
        assert find_violations({"twitter": _tweet("x" * 270)}) == {}

    def test_hashtags_fazem_estourar(self):
        # 270 de texto + 2 + "#marketing" (10) = 282 > 280
        result = find_violations({"twitter": _tweet("x" * 270, ["marketing"])})
        assert result == {"twitter": 282}

    def test_thread_checa_cada_tweet(self):
        ok = _tweet("", is_thread=True, thread_parts=["a" * 280, "b" * 200])
        ruim = _tweet("", is_thread=True, thread_parts=["a" * 281, "b" * 10])
        assert find_violations({"twitter": ok}) == {}
        assert find_violations({"twitter": ruim}) == {"twitter": 281}

    def test_hashtags_contam_so_no_ultimo_tweet_da_thread(self):
        c = _tweet("", ["tag"], is_thread=True, thread_parts=["a" * 280, "b" * 276])
        # último: 276 + 2 + 4 = 282
        assert find_violations({"twitter": c}) == {"twitter": 282}

    def test_linkedin_tem_limite_proprio(self):
        ok = AdaptedContent(platform="linkedin", text="x" * 2900)
        ruim = AdaptedContent(platform="linkedin", text="x" * 3001)
        assert find_violations({"linkedin": ok}) == {}
        assert "linkedin" in find_violations({"linkedin": ruim})


class TestEnsureWithinLimits:
    def test_nao_chama_a_ia_quando_tudo_cabe(self):
        model = MagicMock()
        results = {"twitter": _tweet("curto")}
        ensure_within_limits(model, results)
        model.generate_content.assert_not_called()

    def test_pede_versao_mais_curta_e_usa_a_nova(self):
        model = MagicMock()
        model.generate_content.return_value = _resp(
            {"twitter": {"text": "versão curta", "hashtags": ["mkt"], "is_thread": False}}
        )
        results = {
            "twitter": _tweet("x" * 300),
            "linkedin": AdaptedContent(platform="linkedin", text="ok"),
        }
        out = ensure_within_limits(model, results)

        assert out["twitter"].text == "versão curta"
        assert out["linkedin"].text == "ok"  # o que já cabia não muda
        prompt = model.generate_content.call_args[0][0]
        assert "TWITTER" in prompt and "300 caracteres" in prompt and "280" in prompt
        assert "LINKEDIN" not in prompt  # só pede o que estourou

    def test_desiste_depois_das_tentativas_e_corta_no_fim_da_palavra(self):
        model = MagicMock()
        longo = "palavra " * 60  # 480 caracteres
        model.generate_content.return_value = _resp(
            {"twitter": {"text": longo, "hashtags": ["mkt"], "is_thread": False}}
        )
        out = ensure_within_limits(model, {"twitter": _tweet(longo, ["mkt"])})

        assert model.generate_content.call_count == MAX_TENTATIVAS_REESCRITA
        assert final_length(out["twitter"].text, ["mkt"]) <= TWEET_MAX
        assert out["twitter"].text.endswith("palavra…")

    def test_resposta_invalida_da_ia_nao_quebra(self):
        model = MagicMock()
        bad = MagicMock()
        bad.text = "isso não é JSON"
        model.generate_content.return_value = bad
        out = ensure_within_limits(model, {"twitter": _tweet("y " * 200)})
        assert find_violations(out) == {}


class TestAdaptContentFluxoCompleto:
    def test_gera_valida_e_reescreve(self, monkeypatch):
        primeira = _resp({"twitter": {"text": "z" * 400, "hashtags": [], "is_thread": False}})
        segunda = _resp({"twitter": {"text": "agora cabe", "hashtags": [], "is_thread": False}})
        model = MagicMock()
        model.generate_content.side_effect = [primeira, segunda]
        monkeypatch.setattr("google.generativeai.GenerativeModel", lambda **kw: model)

        out = adapt_content("conteúdo original", platforms=["twitter"])

        assert out["twitter"].text == "agora cabe"
        assert model.generate_content.call_count == 2
