"""core/audit.py — Log de auditoria e análise de sentimento."""
import json
import logging
from typing import Optional
from flask import request

log = logging.getLogger(__name__)


def log_action(action: str, resource_type: str = None,
               resource_id=None, details: dict = None, user_id: int = None) -> None:
    """Registra uma ação no log de auditoria."""
    try:
        from core.models import AuditLog, db
        from flask_login import current_user

        uid = user_id
        if uid is None:
            try:
                uid = current_user.id if current_user and current_user.is_authenticated else None
            except Exception:
                uid = None

        entry = AuditLog(
            user_id=user_id or uid,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=request.remote_addr if request else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:
        log.error("Falha ao registrar auditoria: %s", exc)


def analyze_sentiment(comments: list[str]) -> dict:
    """
    Analisa o sentimento de uma lista de comentários usando Gemini.
    Retorna proporções positivo/neutro/negativo e temas principais.
    """
    if not comments:
        return {"positive": 0, "neutral": 0, "negative": 0, "summary": "Sem comentários.", "themes": []}

    import google.generativeai as genai
    import re
    from config import config
    genai.configure(api_key=config.gemini_api_key)

    sample = comments[:50]
    text = "\n".join(f"- {c}" for c in sample)

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        f"Analise o sentimento dos comentários abaixo sobre uma marca nas redes sociais.\n\n"
        f"Comentários:\n{text}\n\n"
        f"Responda APENAS com JSON válido:\n"
        f'{{"positive": <0-100>, "neutral": <0-100>, "negative": <0-100>, '
        f'"summary": "resumo em 1 frase", "themes": ["tema1", "tema2", "tema3"]}}'
    )
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def suggest_best_time(platform: str, log_entries: list[dict]) -> dict:
    """
    Sugere o melhor horário para postar em uma plataforma
    baseado no histórico de publicações.
    """
    from collections import defaultdict

    hour_counts: dict[int, int] = defaultdict(int)
    day_counts: dict[int, int] = defaultdict(int)

    for entry in log_entries:
        ts = entry.get("timestamp", "")
        if not ts:
            continue
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts)
            hour_counts[dt.hour] += 1
            day_counts[dt.weekday()] += 1
        except Exception:
            continue

    if not hour_counts:
        defaults = {
            "twitter":   {"hour": 9,  "day": 1, "reason": "Terças de manhã têm alto engajamento no Twitter"},
            "instagram": {"hour": 11, "day": 2, "reason": "Quartas ao meio-dia são pico no Instagram"},
            "linkedin":  {"hour": 8,  "day": 1, "reason": "Terças cedo são ideais para conteúdo profissional"},
            "facebook":  {"hour": 13, "day": 3, "reason": "Quintas à tarde têm bom alcance no Facebook"},
            "youtube":   {"hour": 15, "day": 4, "reason": "Sextas à tarde são pico para Community Posts"},
        }
        return defaults.get(platform, {"hour": 10, "day": 1, "reason": "Horário padrão recomendado"})

    best_hour = max(hour_counts, key=hour_counts.get)
    best_day  = max(day_counts,  key=day_counts.get)
    days = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    return {
        "hour": best_hour,
        "day": best_day,
        "reason": f"Baseado no seu histórico: {days[best_day]}s às {best_hour:02d}h têm mais publicações bem-sucedidas"
    }


def generate_ab_variants(original_text: str, platforms: list[str]) -> tuple[dict, dict]:
    """
    Gera duas versões (A e B) do conteúdo com ângulos diferentes.
    Retorna dois dicionários de AdaptedContent.
    """
    from core.ai_processor import adapt_content

    import google.generativeai as genai
    import re, json
    from config import config
    genai.configure(api_key=config.gemini_api_key)

    model = genai.GenerativeModel("gemini-1.5-flash")
    r = model.generate_content(
        f"Reescreva o texto abaixo de duas formas diferentes para um teste A/B:\n\n"
        f"Original: {original_text}\n\n"
        f"Variante A: foque em BENEFÍCIOS emocionais e storytelling.\n"
        f"Variante B: foque em DADOS, fatos e argumentos racionais.\n\n"
        f'Responda APENAS com JSON: {{"a": "texto variante A", "b": "texto variante B"}}'
    )
    raw = re.sub(r"^```(?:json)?\s*", "", r.text.strip())
    raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)

    adapted_a = adapt_content(data["a"], platforms=platforms)
    adapted_b = adapt_content(data["b"], platforms=platforms)
    return adapted_a, adapted_b
