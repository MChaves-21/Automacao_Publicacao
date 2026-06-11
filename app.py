"""app.py — Fábrica Flask com rate limiting e todas as integrações."""
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from auth import auth_bp, login_manager, seed_admin
from config import config
from core.models import db
from routes.api import api_bp
from routes.api_posts import posts_bp
from routes.api_tools import tools_bp
from routes.api_integrations import integrations_bp
from routes.views import views_bp
from routes.youtube_auth import youtube_bp

limiter = Limiter(key_func=get_remote_address, default_limits=["300 per hour"],
                  storage_uri="memory://")

def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    db_url = config.sqlalchemy_database_url
    if test_config and "SQLALCHEMY_DATABASE_URI" in test_config:
        db_url = test_config["SQLALCHEMY_DATABASE_URI"]

    app.config.update(
        SECRET_KEY=config.flask_secret_key,
        SQLALCHEMY_DATABASE_URI=db_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        RATELIMIT_ENABLED=True,
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Limites específicos por blueprint/rota
    limiter.limit("60 per minute")(api_bp)
    limiter.limit("30 per minute")(posts_bp)
    limiter.limit("10 per minute; 100 per hour")(integrations_bp)

    for bp in [auth_bp, views_bp, api_bp, posts_bp, tools_bp, integrations_bp, youtube_bp]:
        app.register_blueprint(bp)

    # Servir uploads locais
    from flask import send_from_directory
    import os

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        upload_folder = os.path.join(app.root_path, "uploads")
        return send_from_directory(upload_folder, filename)

    with app.app_context():
        db.create_all()
        seed_admin()

    return app
