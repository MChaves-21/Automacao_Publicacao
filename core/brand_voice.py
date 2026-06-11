"""core/brand_voice.py — Gerencia e aplica a voz da marca nos prompts do Gemini."""
import logging
from typing import Optional

log = logging.getLogger(__name__)


def get_active_voice() -> Optional[dict]:
    """Retorna a brand voice ativa do banco, ou None."""
    try:
        from core.models import BrandVoice
        bv = BrandVoice.query.filter_by(is_active=True).order_by(BrandVoice.created_at.desc()).first()
        return bv.to_dict() if bv else None
    except Exception as exc:
        log.warning("Não foi possível carregar brand voice: %s", exc)
        return None


def build_voice_instruction(voice: dict) -> str:
    """Gera instrução de sistema para o Gemini baseada na brand voice."""
    if not voice:
        return ""

    parts = [f"\n\n=== IDENTIDADE DA MARCA ===",
             f"Nome: {voice.get('name', '')}"]

    if voice.get("description"):
        parts.append(f"Descrição: {voice['description']}")

    tone_map = {
        "profissional": "Use linguagem formal, objetiva e que transmita autoridade.",
        "casual":       "Use linguagem descontraída, próxima e acessível.",
        "inspiracional":"Use linguagem motivadora, positiva e que inspire ação.",
        "divertido":    "Use humor leve, emojis e linguagem jovem e criativa.",
        "educativo":    "Use linguagem clara, didática e que ensine algo útil.",
    }
    tone = voice.get("tone", "profissional")
    parts.append(f"Tom: {tone_map.get(tone, tone)}")

    if voice.get("keywords"):
        kws = ", ".join(voice["keywords"])
        parts.append(f"Palavras-chave para incluir quando relevante: {kws}")

    if voice.get("avoid_words"):
        avd = ", ".join(voice["avoid_words"])
        parts.append(f"Palavras/expressões a EVITAR: {avd}")

    if voice.get("example_post"):
        parts.append(f"Exemplo de post ideal da marca:\n{voice['example_post'][:400]}")

    parts.append("Aplique esta identidade em TODO o conteúdo gerado.")
    return "\n".join(parts)


def score_post(content: str, platforms: list[str]) -> dict:
    """
    Usa Gemini para avaliar o potencial de engajamento do post.
    Retorna score 1-10, pontos fortes e sugestões de melhoria.
    """
    import json, re
    import google.generativeai as genai
    from config import config

    genai.configure(api_key=config.gemini_api_key)
    voice = get_active_voice()
    voice_ctx = build_voice_instruction(voice) if voice else ""

    prompt = (
        f"Analise este post de marketing e gere uma pontuação de engajamento previsto "
        f"para as plataformas: {', '.join(platforms)}.\n\n"
        f"Post:\n{content}\n"
        f"{voice_ctx}\n\n"
        f"Responda APENAS em JSON válido:\n"
        f'{{"score": <1-10>, "summary": "avaliação em 1 frase", '
        f'"strengths": ["ponto1","ponto2"], "improvements": ["sugestão1","sugestão2"], '
        f'"by_platform": {{"twitter": <1-10>, "instagram": <1-10>, "linkedin": <1-10>}}}}'
    )

    model = genai.GenerativeModel("gemini-1.5-flash")
    resp  = model.generate_content(prompt)
    raw   = re.sub(r"^```(?:json)?\s*", "", resp.text.strip())
    raw   = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)
