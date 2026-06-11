"""core/models.py — Todos os modelos do banco de dados."""
import uuid
from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

class UserRole:
    ADMIN    = "admin"    # tudo: publicar, aprovar, gerenciar usuários
    REVIEWER = "revisor"  # aprovar/rejeitar posts
    EDITOR   = "editor"   # criar e enviar para revisão

class PostStatus:
    DRAFT     = "draft"
    PENDING   = "pending_review"
    APPROVED  = "approved"
    PUBLISHED = "published"
    REJECTED  = "rejected"
    FAILED    = "failed"

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), default=UserRole.EDITOR, nullable=False)
    otp_secret    = db.Column(db.String(32))
    otp_enabled   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    is_active     = db.Column(db.Boolean, default=True)

    youtube_token = db.relationship("YouTubeToken", back_populates="user", uselist=False, cascade="all, delete-orphan")
    posts         = db.relationship("Post", foreign_keys="Post.author_id", back_populates="author")

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)

    @property
    def is_admin(self): return self.role == UserRole.ADMIN
    @property
    def can_review(self): return self.role in (UserRole.ADMIN, UserRole.REVIEWER)
    @property
    def can_publish_direct(self): return self.role == UserRole.ADMIN

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email,
                "role": self.role, "otp_enabled": self.otp_enabled,
                "created_at": self.created_at.isoformat() if self.created_at else None}

class YouTubeToken(db.Model):
    __tablename__ = "youtube_tokens"
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    access_token  = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_expiry  = db.Column(db.DateTime)
    channel_id    = db.Column(db.String(100))
    channel_name  = db.Column(db.String(200))
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user          = db.relationship("User", back_populates="youtube_token")

    def to_credentials_dict(self):
        return {"token": self.access_token, "refresh_token": self.refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": None, "client_secret": None,
                "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"]}

class Post(db.Model):
    __tablename__ = "posts"
    id               = db.Column(db.Integer, primary_key=True)
    author_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewer_id      = db.Column(db.Integer, db.ForeignKey("users.id"))
    content          = db.Column(db.Text, nullable=False)
    image_url        = db.Column(db.String(1000))
    image_prompt     = db.Column(db.String(500))
    platforms        = db.Column(db.JSON, nullable=False)
    adapted_content  = db.Column(db.JSON)
    status           = db.Column(db.String(20), default=PostStatus.DRAFT, nullable=False, index=True)
    scheduled_at     = db.Column(db.DateTime)
    published_at     = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    ab_variant       = db.Column(db.String(1))
    ab_group_id      = db.Column(db.String(36))
    results          = db.Column(db.JSON)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author           = db.relationship("User", foreign_keys=[author_id], back_populates="posts")
    reviewer         = db.relationship("User", foreign_keys=[reviewer_id])

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "image_url": self.image_url,
            "platforms": self.platforms or [],
            "status": self.status,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "rejection_reason": self.rejection_reason,
            "ab_variant": self.ab_variant,
            "ab_group_id": self.ab_group_id,
            "results": self.results,
            "author": {"id": self.author.id, "username": self.author.username} if self.author else None,
            "reviewer": {"id": self.reviewer.id, "username": self.reviewer.username} if self.reviewer else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class Template(db.Model):
    __tablename__ = "templates"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    content     = db.Column(db.Text, nullable=False)
    platforms   = db.Column(db.JSON)
    category    = db.Column(db.String(50))
    author_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    author      = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description,
                "content": self.content, "platforms": self.platforms,
                "category": self.category,
                "author": self.author.username if self.author else None,
                "created_at": self.created_at.isoformat() if self.created_at else None}

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"))
    action        = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))
    resource_id   = db.Column(db.String(50))
    details       = db.Column(db.JSON)
    ip_address    = db.Column(db.String(45))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    user          = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "user": self.user.username if self.user else "sistema",
                "action": self.action, "resource_type": self.resource_type,
                "resource_id": self.resource_id, "details": self.details,
                "created_at": self.created_at.isoformat() if self.created_at else None}


# ── Brand Voice ───────────────────────────────────────────────────────────────

class BrandVoice(db.Model):
    __tablename__ = "brand_voices"
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)
    tone         = db.Column(db.String(50), default="profissional")
    description  = db.Column(db.Text)
    keywords     = db.Column(db.JSON, default=list)
    avoid_words  = db.Column(db.JSON, default=list)
    example_post = db.Column(db.Text)
    is_active    = db.Column(db.Boolean, default=True)
    author_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    author       = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "tone": self.tone,
                "description": self.description, "keywords": self.keywords or [],
                "avoid_words": self.avoid_words or [], "example_post": self.example_post,
                "is_active": self.is_active,
                "created_at": self.created_at.isoformat() if self.created_at else None}


# ── RSS Feed ──────────────────────────────────────────────────────────────────

class RssFeed(db.Model):
    __tablename__ = "rss_feeds"
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    url            = db.Column(db.String(500), nullable=False)
    platforms      = db.Column(db.JSON, default=list)
    interval_hours = db.Column(db.Integer, default=6)
    last_checked   = db.Column(db.DateTime)
    last_entry_id  = db.Column(db.String(500))
    is_active      = db.Column(db.Boolean, default=True)
    author_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    author         = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "url": self.url,
                "platforms": self.platforms or [], "interval_hours": self.interval_hours,
                "last_checked": self.last_checked.isoformat() if self.last_checked else None,
                "is_active": self.is_active}


# ── Webhook ───────────────────────────────────────────────────────────────────

class Webhook(db.Model):
    __tablename__ = "webhooks"
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    url            = db.Column(db.String(500), nullable=False)
    events         = db.Column(db.JSON, default=list)
    secret         = db.Column(db.String(64))
    is_active      = db.Column(db.Boolean, default=True)
    last_triggered = db.Column(db.DateTime)
    last_status    = db.Column(db.Integer)
    author_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    author         = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "url": self.url,
                "events": self.events or [], "is_active": self.is_active,
                "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
                "last_status": self.last_status}
