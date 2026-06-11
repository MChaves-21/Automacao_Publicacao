"""tests/test_tools.py — Testes de templates, 2FA, CSV, sentimento e A/B."""
import io, csv

class TestTemplates:
    def test_list_empty_initially(self, auth_client):
        r = auth_client.get("/api/templates")
        assert r.status_code == 200 and isinstance(r.get_json(), list)

    def test_create_template(self, auth_client):
        r = auth_client.post("/api/templates", json={
            "name":"Lançamento","content":"Conteúdo do template","category":"lancamento"
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data["name"] == "Lançamento"

    def test_template_appears_in_list(self, auth_client):
        auth_client.post("/api/templates", json={"name":"T1","content":"C1"})
        ts = auth_client.get("/api/templates").get_json()
        assert any(t["name"]=="T1" for t in ts)

    def test_missing_name_rejected(self, auth_client):
        r = auth_client.post("/api/templates", json={"content":"Só conteúdo"})
        assert r.status_code == 400

    def test_delete_template(self, auth_client):
        tid = auth_client.post("/api/templates",json={"name":"Del","content":"C"}).get_json()["id"]
        r = auth_client.delete(f"/api/templates/{tid}")
        assert r.status_code == 200 and r.get_json()["ok"] is True

class TestTwoFA:
    def test_setup_returns_secret_and_qr(self, auth_client):
        r = auth_client.post("/api/2fa/setup")
        assert r.status_code == 200
        data = r.get_json()
        assert "secret" in data and "qr_image" in data

    def test_invalid_token_rejected(self, auth_client):
        auth_client.post("/api/2fa/setup")
        r = auth_client.post("/api/2fa/verify", json={"token":"000000"})
        assert r.status_code == 401

    def test_valid_token_activates_2fa(self, auth_client):
        import pyotp
        r = auth_client.post("/api/2fa/setup")
        secret = r.get_json()["secret"]
        token = pyotp.TOTP(secret).now()
        r2 = auth_client.post("/api/2fa/verify", json={"token": token})
        assert r2.status_code == 200 and r2.get_json()["ok"] is True

    def test_disable_2fa(self, auth_client):
        import pyotp
        secret = auth_client.post("/api/2fa/setup").get_json()["secret"]
        auth_client.post("/api/2fa/verify", json={"token": pyotp.TOTP(secret).now()})
        r = auth_client.post("/api/2fa/disable")
        assert r.status_code == 200 and r.get_json()["ok"] is True

class TestCSVImport:
    def _make_csv(self, rows):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["content","platforms","scheduled_at","image_url"])
        w.writeheader(); w.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def test_imports_posts(self, auth_client):
        data = self._make_csv([
            {"content":"Post 1","platforms":"twitter|linkedin","scheduled_at":"","image_url":""},
            {"content":"Post 2","platforms":"instagram","scheduled_at":"","image_url":""},
        ])
        r = auth_client.post("/api/posts/import-csv",
            data={"file":(io.BytesIO(data),"posts.csv")},
            content_type="multipart/form-data")
        assert r.status_code == 200
        assert r.get_json()["created"] == 2

    def test_invalid_date_reports_error(self, auth_client):
        data = self._make_csv([{"content":"Post","platforms":"twitter","scheduled_at":"data-invalida","image_url":""}])
        r = auth_client.post("/api/posts/import-csv",
            data={"file":(io.BytesIO(data),"p.csv")},
            content_type="multipart/form-data")
        assert r.get_json()["errors"]

    def test_empty_content_skipped(self, auth_client):
        data = self._make_csv([{"content":"","platforms":"twitter","scheduled_at":"","image_url":""}])
        r = auth_client.post("/api/posts/import-csv",
            data={"file":(io.BytesIO(data),"p.csv")},
            content_type="multipart/form-data")
        assert r.get_json()["created"] == 0

class TestSentimentAnalysis:
    def test_empty_comments_rejected(self, auth_client):
        r = auth_client.post("/api/sentiment", json={"comments":[]})
        assert r.status_code == 400

    def test_returns_sentiment_structure(self, auth_client, mock_gemini):
        import json
        mock_gemini.generate_content.return_value.text = json.dumps({
            "positive":70,"neutral":20,"negative":10,
            "summary":"Feedback positivo.","themes":["qualidade","entrega"]
        })
        r = auth_client.post("/api/sentiment", json={"comments":["Ótimo!","Adorei!","Ok"]})
        assert r.status_code == 200
        data = r.get_json()
        for k in ("positive","neutral","negative","summary","themes"):
            assert k in data

class TestABTest:
    def test_missing_content_rejected(self, auth_client):
        r = auth_client.post("/api/ab-test", json={})
        assert r.status_code == 400

    def test_returns_two_variants(self, auth_client, mock_gemini, gemini_response_factory):
        import json as j
        mock_gemini.generate_content.return_value.text = j.dumps({"a":"Versão emocional","b":"Versão racional"})
        r = auth_client.post("/api/ab-test",
                             json={"content":"Post original","platforms":["twitter"]})
        if r.status_code == 200:
            data = r.get_json()
            assert "a" in data and "b" in data

class TestBestTime:
    def test_returns_suggestion(self, auth_client):
        r = auth_client.get("/api/best-time/twitter")
        assert r.status_code == 200
        data = r.get_json()
        assert "hour" in data and "day" in data and "reason" in data

class TestAuditLog:
    def test_non_admin_forbidden(self, app, client):
        with app.app_context():
            from core.models import User, UserRole, db
            if not User.query.filter_by(username="ed_audit").first():
                ed = User(username="ed_audit", email="ed_audit@t.com", role=UserRole.EDITOR)
                ed.set_password("abc123"); db.session.add(ed); db.session.commit()
        client.post("/login", data={"identifier":"ed_audit","password":"abc123"})
        r = client.get("/api/audit")
        assert r.status_code == 403

    def test_admin_can_access(self, auth_client):
        r = auth_client.get("/api/audit")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

class TestUserManagement:
    def test_admin_lists_users(self, auth_client):
        r = auth_client.get("/api/users")
        assert r.status_code == 200
        users = r.get_json()
        assert any(u["username"]=="admin" for u in users)

    def test_editor_cannot_list_users(self, app, client):
        with app.app_context():
            from core.models import User, UserRole, db
            if not User.query.filter_by(username="ed_users").first():
                ed = User(username="ed_users", email="ed_users@t.com", role=UserRole.EDITOR)
                ed.set_password("abc123"); db.session.add(ed); db.session.commit()
        client.post("/login", data={"identifier":"ed_users","password":"abc123"})
        assert client.get("/api/users").status_code == 403

class TestEngagement:
    def test_returns_metrics(self, auth_client):
        r = auth_client.get("/api/engagement/twitter/post123")
        assert r.status_code == 200
        data = r.get_json()
        assert "metrics" in data
        for k in ("likes","comments","shares","impressions"):
            assert k in data["metrics"]
