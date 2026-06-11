"""core/email_service.py — Notificações por e-mail via SMTP."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import config

log = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str) -> bool:
    if not config.smtp_host or not config.smtp_user:
        log.warning("SMTP não configurado — e-mail não enviado para %s", to)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = config.smtp_from or config.smtp_user
        msg["To"]      = to
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL(config.smtp_host, int(config.smtp_port or 465)) as s:
            s.login(config.smtp_user, config.smtp_pass)
            s.sendmail(msg["From"], to, msg.as_string())
        return True
    except Exception as exc:
        log.error("Falha ao enviar e-mail: %s", exc)
        return False


def _base(title: str, body: str) -> str:
    return f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;color:#1a1a2e">
  <div style="font-size:20px;font-weight:700;margin-bottom:4px">📣 MktAutomation</div>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:12px 0 20px">
  <h2 style="font-size:16px;font-weight:600;margin-bottom:12px">{title}</h2>
  {body}
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0 12px">
  <p style="font-size:12px;color:#9ca3af">Marketing Automation · Powered by Gemini Flash</p>
</div>"""


def notify_pending_review(reviewer_email: str, post_id: int, author: str, preview: str) -> bool:
    return _send(reviewer_email, "📋 Post aguardando sua aprovação",
        _base("Post aguardando aprovação",
              f"<p><strong>{author}</strong> enviou um post para revisão.</p>"
              f"<p style='background:#f3f4f6;padding:12px;border-radius:8px;font-size:13px'>{preview[:200]}...</p>"
              f"<a href='{config.app_url}/api/posts/{post_id}' style='display:inline-block;background:#f0a020;"
              f"color:#07090d;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:12px'>"
              f"Ver no painel →</a>"))


def notify_approved(author_email: str, post_id: int) -> bool:
    return _send(author_email, "✅ Seu post foi aprovado",
        _base("Post aprovado!", "<p>Seu post foi aprovado e será publicado no horário agendado.</p>"))


def notify_rejected(author_email: str, reason: str) -> bool:
    return _send(author_email, "❌ Post precisa de ajustes",
        _base("Post devolvido para edição",
              f"<p>Seu post foi devolvido para edição com o seguinte feedback:</p>"
              f"<p style='background:#fef2f2;padding:12px;border-radius:8px;color:#991b1b'>{reason}</p>"))


def notify_published(author_email: str, platforms: list[str]) -> bool:
    plats = ", ".join(platforms)
    return _send(author_email, f"🚀 Post publicado em {plats}",
        _base("Post publicado com sucesso!",
              f"<p>Seu post foi publicado nas seguintes plataformas: <strong>{plats}</strong></p>"))


def notify_failed(author_email: str, platform: str, error: str) -> bool:
    return _send(author_email, f"⚠️ Falha ao publicar no {platform}",
        _base(f"Erro ao publicar no {platform}",
              f"<p>Não foi possível publicar no <strong>{platform}</strong>.</p>"
              f"<p style='background:#fef2f2;padding:12px;border-radius:8px;color:#991b1b;font-size:12px'>{error}</p>"))
