"""
routes/youtube_auth.py — Fluxo OAuth 2.0 para conectar canal do YouTube.
"""
import json
from datetime import datetime

from flask import Blueprint, jsonify, redirect, request, session, url_for
from flask_login import current_user, login_required
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config import config

youtube_bp = Blueprint("youtube", __name__, url_prefix="/youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def _make_flow() -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": config.youtube_client_id,
                "client_secret": config.youtube_client_secret,
                "redirect_uris": [config.youtube_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=config.youtube_redirect_uri,
    )


@youtube_bp.get("/auth")
@login_required
def auth():
    """Inicia o fluxo OAuth — redireciona para o Google."""
    if not config.youtube_client_id:
        return jsonify({"error": "YOUTUBE_CLIENT_ID não configurado."}), 400

    flow = _make_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@youtube_bp.get("/callback")
@login_required
def callback():
    """Recebe o código do Google, troca por tokens e salva no banco."""
    from core.models import YouTubeToken, db

    state = session.get("oauth_state")
    flow = _make_flow()
    flow.fetch_token(authorization_response=request.url, state=state)

    creds: Credentials = flow.credentials

    # Busca info do canal
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])

    channel_id   = items[0]["id"] if items else None
    channel_name = items[0]["snippet"]["title"] if items else "Meu Canal"

    # Salva ou atualiza token no banco
    token = YouTubeToken.query.filter_by(user_id=current_user.id).first()
    if not token:
        token = YouTubeToken(user_id=current_user.id)
        db.session.add(token)

    token.access_token  = creds.token
    token.refresh_token = creds.refresh_token
    token.token_expiry  = creds.expiry
    token.channel_id    = channel_id
    token.channel_name  = channel_name
    db.session.commit()

    return redirect(url_for("views.index") + "?youtube=connected")


@youtube_bp.delete("/disconnect")
@login_required
def disconnect():
    """Remove a conexão do canal do YouTube do usuário atual."""
    from core.models import YouTubeToken, db

    token = YouTubeToken.query.filter_by(user_id=current_user.id).first()
    if token:
        db.session.delete(token)
        db.session.commit()
    return jsonify({"ok": True})


@youtube_bp.get("/status")
@login_required
def status():
    """Retorna o status da conexão YouTube do usuário atual."""
    from core.publishers.youtube import get_channel_info

    info = get_channel_info(current_user.id)
    if info:
        return jsonify({"connected": True, **info})
    return jsonify({"connected": False})
