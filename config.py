"""config.py — Configuração centralizada."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
load_dotenv()

@dataclass
class Config:
    # ── IA ────────────────────────────────────────────────
    gemini_api_key:  str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    openai_api_key:  str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # ── Web / Auth ────────────────────────────────────────
    flask_secret_key: str = field(default_factory=lambda: os.getenv("FLASK_SECRET_KEY", "dev-insecure"))
    admin_username:   str = field(default_factory=lambda: os.getenv("ADMIN_USERNAME", ""))
    admin_password:   str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    admin_email:      str = field(default_factory=lambda: os.getenv("ADMIN_EMAIL", ""))
    app_url:          str = field(default_factory=lambda: os.getenv("APP_URL", "http://localhost:5000"))

    # ── Banco de dados ────────────────────────────────────
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///app.db"))

    # ── E-mail SMTP ───────────────────────────────────────
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: str = field(default_factory=lambda: os.getenv("SMTP_PORT", "465"))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_pass: str = field(default_factory=lambda: os.getenv("SMTP_PASS", ""))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", ""))

    # ── YouTube OAuth ─────────────────────────────────────
    youtube_client_id:     str = field(default_factory=lambda: os.getenv("YOUTUBE_CLIENT_ID", ""))
    youtube_client_secret: str = field(default_factory=lambda: os.getenv("YOUTUBE_CLIENT_SECRET", ""))
    youtube_redirect_uri:  str = field(default_factory=lambda: os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:5000/youtube/callback"))

    # ── Twitter / X ───────────────────────────────────────
    twitter_api_key:     str = field(default_factory=lambda: os.getenv("TWITTER_API_KEY", ""))
    twitter_api_secret:  str = field(default_factory=lambda: os.getenv("TWITTER_API_SECRET", ""))
    twitter_access_token:str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN", ""))
    twitter_access_secret:str= field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN_SECRET", ""))
    twitter_bearer_token: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))

    # ── Instagram / Facebook ──────────────────────────────
    instagram_access_token: str = field(default_factory=lambda: os.getenv("INSTAGRAM_ACCESS_TOKEN", ""))
    instagram_account_id:   str = field(default_factory=lambda: os.getenv("INSTAGRAM_ACCOUNT_ID", ""))
    facebook_access_token:  str = field(default_factory=lambda: os.getenv("FACEBOOK_ACCESS_TOKEN", ""))
    facebook_page_id:       str = field(default_factory=lambda: os.getenv("FACEBOOK_PAGE_ID", ""))

    # ── LinkedIn ──────────────────────────────────────────
    linkedin_access_token: str = field(default_factory=lambda: os.getenv("LINKEDIN_ACCESS_TOKEN", ""))
    linkedin_person_urn:   str = field(default_factory=lambda: os.getenv("LINKEDIN_PERSON_URN", ""))

    # ── TikTok ────────────────────────────────────────────
    tiktok_access_token: str = field(default_factory=lambda: os.getenv("TIKTOK_ACCESS_TOKEN", ""))
    tiktok_open_id:      str = field(default_factory=lambda: os.getenv("TIKTOK_OPEN_ID", ""))

    # ── Pinterest ─────────────────────────────────────────
    pinterest_access_token: str = field(default_factory=lambda: os.getenv("PINTEREST_ACCESS_TOKEN", ""))
    pinterest_board_id:     str = field(default_factory=lambda: os.getenv("PINTEREST_BOARD_ID", ""))

    # ── WhatsApp Business ─────────────────────────────────
    whatsapp_token:     str = field(default_factory=lambda: os.getenv("WHATSAPP_TOKEN", ""))
    whatsapp_phone_id:  str = field(default_factory=lambda: os.getenv("WHATSAPP_PHONE_ID", ""))
    whatsapp_recipient: str = field(default_factory=lambda: os.getenv("WHATSAPP_RECIPIENT", ""))

    # ── Google My Business ────────────────────────────────
    google_access_token: str = field(default_factory=lambda: os.getenv("GOOGLE_ACCESS_TOKEN", ""))
    gmb_location_name:   str = field(default_factory=lambda: os.getenv("GMB_LOCATION_NAME", ""))


    # ── Slack ─────────────────────────────────────────────
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))

    # ── Upload / Cloudinary ───────────────────────────────
    cloudinary_url: str = field(default_factory=lambda: os.getenv("CLOUDINARY_URL", ""))

    # ── Rate Limiting ─────────────────────────────────────
    ratelimit_storage_url: str = field(default_factory=lambda: os.getenv("RATELIMIT_STORAGE_URL", "memory://"))
    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url
        return url.replace("postgres://", "postgresql://", 1) if url.startswith("postgres://") else url

    def missing_keys(self) -> list[str]:
        return [k for k, v in {"GEMINI_API_KEY": self.gemini_api_key,
                                "FLASK_SECRET_KEY": self.flask_secret_key}.items() if not v]

config = Config()
