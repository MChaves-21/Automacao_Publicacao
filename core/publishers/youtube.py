"""
core/publishers/youtube.py — Publica Community Posts no YouTube via OAuth 2.0.

Pré-requisitos:
  - Canal com mais de 500 inscritos (exigência do YouTube para Community Posts)
  - Credenciais OAuth 2.0 configuradas no Google Cloud Console
  - Usuário autorizou o acesso em /youtube/auth

Adapta o conteúdo para o YouTube com tom adequado para a plataforma.
"""
import logging
from typing import Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import config
from core.ai_processor import AdaptedContent

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def _build_credentials(token_dict: dict) -> Credentials:
    """Constrói objeto Credentials e renova o token se necessário."""
    creds = Credentials(
        token=token_dict["access_token"],
        refresh_token=token_dict.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.youtube_client_id,
        client_secret=config.youtube_client_secret,
        scopes=SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _get_token_for_user(user_id: int) -> Optional[dict]:
    """Busca o token do usuário atual no banco de dados."""
    try:
        from core.models import YouTubeToken
        token = YouTubeToken.query.filter_by(user_id=user_id).first()
        if not token:
            return None
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
        }
    except Exception as exc:
        logger.error("Erro ao buscar token YouTube: %s", exc)
        return None


def post(content: AdaptedContent, image_url: Optional[str] = None, user_id: Optional[int] = None) -> dict:
    """
    Publica um Community Post no YouTube.

    Args:
        content: Conteúdo adaptado para o YouTube.
        image_url: URL de imagem opcional.
        user_id: ID do usuário dono do canal.

    Returns:
        Dicionário com resultado da publicação.

    Raises:
        ValueError: Se o token OAuth não estiver configurado.
        Exception: Qualquer erro da API do YouTube.
    """
    if not user_id:
        from flask_login import current_user
        user_id = current_user.id if current_user and current_user.is_authenticated else None

    if not user_id:
        raise ValueError("Usuário não autenticado. Conecte seu canal em Configurações → YouTube.")

    token_dict = _get_token_for_user(user_id)
    if not token_dict:
        raise ValueError(
            "Canal do YouTube não conectado. "
            "Acesse Configurações → YouTube → Conectar canal."
        )

    creds = _build_credentials(token_dict)

    text = content.text
    if content.hashtags:
        hashtag_str = " ".join(f"#{h}" for h in content.hashtags)
        text = f"{text}\n\n{hashtag_str}"

    youtube = build("youtube", "v3", credentials=creds)

    body: dict = {
        "snippet": {
            "type": "TEXT_ONLY",
            "text": text,
        }
    }

    if image_url:
        body["snippet"]["type"] = "IMAGE_AND_TEXT"
        body["snippet"]["imageUrl"] = image_url

    response = youtube.posts().insert(part="snippet", body=body).execute()
    post_id = response.get("id", "")

    # Atualiza token no banco (pode ter renovado)
    _save_refreshed_token(user_id, creds)

    print(f"  ✅ Community Post publicado no YouTube (ID: {post_id})")
    return {"platform": "youtube", "type": "community_post", "id": post_id}


def _save_refreshed_token(user_id: int, creds: Credentials) -> None:
    """Persiste token renovado no banco para evitar expiração."""
    try:
        from core.models import YouTubeToken, db
        token = YouTubeToken.query.filter_by(user_id=user_id).first()
        if token and creds.token:
            token.access_token = creds.token
            if creds.refresh_token:
                token.refresh_token = creds.refresh_token
            db.session.commit()
    except Exception as exc:
        logger.warning("Não foi possível salvar token renovado: %s", exc)


def get_channel_info(user_id: int) -> Optional[dict]:
    """Retorna informações do canal conectado do usuário."""
    token_dict = _get_token_for_user(user_id)
    if not token_dict:
        return None

    try:
        creds = _build_credentials(token_dict)
        youtube = build("youtube", "v3", credentials=creds)
        resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            return None
        ch = items[0]
        return {
            "id": ch["id"],
            "name": ch["snippet"]["title"],
            "thumbnail": ch["snippet"]["thumbnails"]["default"]["url"],
            "subscribers": ch["statistics"].get("subscriberCount", "0"),
        }
    except Exception as exc:
        logger.error("Erro ao buscar info do canal: %s", exc)
        return None
