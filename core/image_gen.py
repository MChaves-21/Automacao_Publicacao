"""core/image_gen.py — Geração de imagens com DALL-E 3 (OpenAI)."""
import logging
from typing import Optional
from config import config

log = logging.getLogger(__name__)


def generate_image(prompt: str, size: str = "1024x1024") -> str:
    """
    Gera uma imagem com DALL-E 3 e retorna a URL.

    Args:
        prompt: Descrição da imagem desejada.
        size: "1024x1024" | "1792x1024" | "1024x1792"

    Returns:
        URL da imagem gerada (válida por 1 hora).

    Raises:
        ValueError: Se OPENAI_API_KEY não estiver configurada.
        Exception: Qualquer erro da API OpenAI.
    """
    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY não configurada. Adicione ao .env para usar geração de imagens.")

    import openai
    client = openai.OpenAI(api_key=config.openai_api_key)

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality="standard",
        n=1,
    )
    url = response.data[0].url
    log.info("Imagem gerada com DALL-E 3: %s...", url[:60])
    return url


def suggest_image_prompt(content: str) -> str:
    """
    Usa o Gemini para sugerir um prompt visual para DALL-E baseado no conteúdo do post.
    """
    import google.generativeai as genai
    from config import config as cfg
    genai.configure(api_key=cfg.gemini_api_key)

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        f"Crie um prompt em inglês para gerar uma imagem profissional de marketing no DALL-E 3 "
        f"para acompanhar este post: '{content[:300]}'. "
        f"O prompt deve descrever uma imagem visualmente impactante, sem texto na imagem, "
        f"estilo fotografia profissional ou ilustração moderna. "
        f"Responda APENAS com o prompt, nada mais."
    )
    return response.text.strip()
