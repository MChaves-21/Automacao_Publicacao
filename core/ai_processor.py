"""
core/ai_processor.py — Adaptação de conteúdo usando Google Gemini Flash (gratuito).
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

from config import config

genai.configure(api_key=config.gemini_api_key)

# ── Constantes ───────────────────────────────────────────────────────────────

PLATFORMS = ("twitter", "instagram", "linkedin", "facebook")

PLATFORM_RULES: dict[str, dict[str, str]] = {
    "twitter": {
        "max_chars": "280",
        "tone": "informal, direto e envolvente",
        "features": "máx 3 hashtags no final; use thread_parts se > 280 chars",
        "format": "curto e impactante",
    },
    "instagram": {
        "max_chars": "2200",
        "tone": "inspirador, visual e com personalidade",
        "features": "caption com CTA, 10-15 hashtags em bloco no final",
        "format": "storytelling, emojis com moderação",
    },
    "linkedin": {
        "max_chars": "3000",
        "tone": "profissional, informativo e que gera valor",
        "features": "3-5 hashtags no final, parágrafos curtos",
        "format": "gancho forte → ideia → pergunta ou insight",
    },
    "facebook": {
        "max_chars": "63206",
        "tone": "conversacional, amigável e engajador",
        "features": "2-3 hashtags, incentiva comentários",
        "format": "storytelling, termina com pergunta",
    },
}

_SYSTEM_PROMPT = """\
Você é um especialista em marketing de conteúdo para redes sociais.
Sua tarefa é adaptar um conteúdo original para diferentes plataformas,
respeitando o tom, limite de caracteres e boas práticas de cada uma.
Responda SEMPRE com JSON válido, sem markdown, sem explicações extras.\
"""

_RESPONSE_SCHEMA = """\
{
  "twitter":   {"text": "...", "hashtags": [...], "is_thread": false, "thread_parts": null},
  "instagram": {"text": "...", "hashtags": [...], "image_description": "..."},
  "linkedin":  {"text": "...", "hashtags": [...]},
  "facebook":  {"text": "...", "hashtags": [...]}
}\
"""


# ── Tipos ────────────────────────────────────────────────────────────────────

@dataclass
class AdaptedContent:
    platform: str
    text: str
    hashtags: list[str] = field(default_factory=list)
    image_description: Optional[str] = None
    is_thread: bool = False
    thread_parts: Optional[list[str]] = None

    @property
    def char_count(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "text": self.text,
            "hashtags": self.hashtags,
            "image_description": self.image_description,
            "is_thread": self.is_thread,
            "thread_parts": self.thread_parts,
            "char_count": self.char_count,
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_markdown_fences(raw: str) -> str:
    """Remove blocos ```json ... ``` que o Gemini eventualmente adiciona."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _build_prompt(original_text: str, platforms: list[str], has_image: bool) -> str:
    specs = "\n".join(
        f"--- {p.upper()} ---\n"
        f"- Tom: {PLATFORM_RULES[p]['tone']}\n"
        f"- Limite: {PLATFORM_RULES[p]['max_chars']} chars\n"
        f"- Recursos: {PLATFORM_RULES[p]['features']}\n"
        f"- Formato: {PLATFORM_RULES[p]['format']}\n"
        for p in platforms
        if p in PLATFORM_RULES
    )

    image_note = "(Acompanha uma imagem)" if has_image else ""

    voice = _get_brand_voice_instruction()
    return (
        f"CONTEÚDO ORIGINAL:\n{original_text}\n{image_note}\n\n"
        f"REGRAS POR PLATAFORMA:\n{specs}\n\n"
        f"Responda com JSON exatamente neste formato:\n{_RESPONSE_SCHEMA}\n\n"
        "Para Twitter: se precisar de mais de 280 chars, "
        "defina is_thread=true e divida em thread_parts (lista, cada item ≤280 chars)."
        + voice
    )


def _parse_response(raw: str, platforms: list[str]) -> dict[str, AdaptedContent]:
    data = json.loads(_strip_markdown_fences(raw))
    return {
        p: AdaptedContent(
            platform=p,
            text=data[p].get("text", ""),
            hashtags=data[p].get("hashtags", []),
            image_description=data[p].get("image_description"),
            is_thread=data[p].get("is_thread", False),
            thread_parts=data[p].get("thread_parts"),
        )
        for p in platforms
        if p in data
    }


# ── API pública ───────────────────────────────────────────────────────────────

def adapt_content(
    original_text: str,
    image_url: Optional[str] = None,
    platforms: Optional[list[str]] = None,
) -> dict[str, AdaptedContent]:
    """
    Analisa o conteúdo e retorna versões adaptadas para cada plataforma.

    Args:
        original_text: Texto original da publicação.
        image_url: URL de imagem opcional para acompanhar o post.
        platforms: Lista de plataformas. Padrão: todas as 4.

    Returns:
        Dicionário {plataforma: AdaptedContent}.

    Raises:
        ValueError: Se original_text for vazio.
        json.JSONDecodeError: Se o Gemini retornar JSON inválido.
        Exception: Qualquer erro da API Gemini.
    """
    if not original_text or not original_text.strip():
        raise ValueError("original_text não pode ser vazio.")

    if platforms is None:
        platforms = list(PLATFORMS)

    platforms = [p for p in platforms if p in PLATFORM_RULES]
    if not platforms:
        raise ValueError(f"Nenhuma plataforma válida. Opções: {PLATFORMS}")

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=_SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(temperature=0.7, max_output_tokens=4096),
    )

    prompt = _build_prompt(original_text, platforms, has_image=bool(image_url))
    response = model.generate_content(prompt)
    return _parse_response(response.text, platforms)


def preview_adapted_content(results: dict[str, AdaptedContent]) -> None:
    """Imprime um preview formatado no terminal."""
    icons = {"twitter": "🐦", "instagram": "📸", "linkedin": "💼", "facebook": "📘"}
    print("\n" + "=" * 60)
    print("📋 PREVIEW  [Gemini Flash]")
    print("=" * 60)

    for platform, content in results.items():
        print(f"\n{icons.get(platform, '📱')} {platform.upper()}")
        print("-" * 40)
        if content.is_thread and content.thread_parts:
            for i, part in enumerate(content.thread_parts, 1):
                print(f"  [{i}/{len(content.thread_parts)}] {part}")
        else:
            print(content.text)
        if content.hashtags:
            print("\n#️⃣", " ".join(f"#{h}" for h in content.hashtags))
        if content.image_description:
            print(f"\n🖼️  {content.image_description}")
        print(f"\n📊 {content.char_count} caracteres")

    print("\n" + "=" * 60)

# Adicionar regra do YouTube ao dicionário PLATFORM_RULES existente
PLATFORM_RULES["youtube"] = {
    "max_chars": "5000",
    "tone": "engajador, informativo e que agrega valor ao canal",
    "features": "sem excesso de hashtags, foco em conteúdo de qualidade, CTA para inscrição",
    "format": "gancho forte, conteúdo de valor, termina com call-to-action para comentários",
}


# ── Brand Voice injetada nos prompts ─────────────────────────────────────────

def _get_brand_voice_instruction() -> str:
    """Retorna instrução de brand voice para injetar no prompt, se houver."""
    try:
        from core.brand_voice import get_active_voice, build_voice_instruction
        voice = get_active_voice()
        return build_voice_instruction(voice) if voice else ""
    except Exception:
        return ""
