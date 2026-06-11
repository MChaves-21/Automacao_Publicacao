"""tests/conftest.py — Fixtures compartilhadas."""
import json, os
from unittest.mock import MagicMock, patch
import pytest

os.environ.setdefault("GEMINI_API_KEY",   "fake-gemini-key")
os.environ.setdefault("OPENAI_API_KEY",   "fake-openai-key")
os.environ.setdefault("ADMIN_USERNAME",   "admin")
os.environ.setdefault("ADMIN_PASSWORD",   "senha123")
os.environ.setdefault("ADMIN_EMAIL",      "admin@test.com")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")

@pytest.fixture(scope="session")
def gemini_response_factory():
    def _make(platforms=None):
        platforms = platforms or ["twitter","instagram","linkedin","facebook"]
        data = {}
        if "twitter"   in platforms: data["twitter"]   = {"text":"Tweet teste!","hashtags":["mkt"],"is_thread":False,"thread_parts":None}
        if "instagram" in platforms: data["instagram"] = {"text":"Caption ✨","hashtags":["insta","mkt"],"image_description":"Imagem colorida"}
        if "linkedin"  in platforms: data["linkedin"]  = {"text":"Post LinkedIn.","hashtags":["ln"]}
        if "facebook"  in platforms: data["facebook"]  = {"text":"Post Facebook!","hashtags":["fb"]}
        if "youtube"   in platforms: data["youtube"]   = {"text":"Community post!","hashtags":["yt"]}
        return json.dumps(data)
    return _make

@pytest.fixture
def mock_gemini(gemini_response_factory):
    mock_response = MagicMock()
    mock_response.text = gemini_response_factory()
    with patch("google.generativeai.GenerativeModel") as mock_class:
        mock_inst = MagicMock()
        mock_inst.generate_content.return_value = mock_response
        mock_class.return_value = mock_inst
        yield mock_inst

@pytest.fixture
def app(tmp_path):
    import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    log_file = tmp_path / "test_log.json"
    with patch("core.scheduler.LOG_FILE", log_file):
        from app import create_app
        flask_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/test.db",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        })
        yield flask_app

@pytest.fixture
def client(app): return app.test_client()

@pytest.fixture
def auth_client(client):
    client.post("/login", data={"identifier": "admin", "password": "senha123"})
    return client

@pytest.fixture
def admin_user(app):
    with app.app_context():
        from core.models import User
        return User.query.filter_by(username="admin").first()
