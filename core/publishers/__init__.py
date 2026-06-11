"""core/publishers/__init__.py — Registro de todos os publishers."""
from typing import Callable, Optional
from core.ai_processor import AdaptedContent

PublisherFn = Callable[[AdaptedContent, Optional[str]], dict]

from core.publishers import twitter, instagram, linkedin, facebook, youtube
from core.publishers import tiktok, pinterest, whatsapp, gmb

PUBLISHERS: dict[str, PublisherFn] = {
    "twitter":   twitter.post,
    "instagram": instagram.post,
    "linkedin":  linkedin.post,
    "facebook":  facebook.post,
    "youtube":   youtube.post,
    "tiktok":    tiktok.post,
    "pinterest": pinterest.post,
    "whatsapp":  whatsapp.post,
    "gmb":       gmb.post,
}
