"""tests/test_posts.py — Testes do fluxo de aprovação de posts."""
from datetime import datetime, timedelta

def future(): return (datetime.now()+timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")

class TestCreatePost:
    def test_creates_draft(self, auth_client):
        r = auth_client.post("/api/posts", json={"content":"Teste","platforms":["twitter"]})
        assert r.status_code == 201

    def test_missing_content_rejected(self, auth_client):
        r = auth_client.post("/api/posts", json={"platforms":["twitter"]})
        assert r.status_code == 400

    def test_missing_platforms_rejected(self, auth_client):
        r = auth_client.post("/api/posts", json={"content":"Texto"})
        assert r.status_code == 400

    def test_with_schedule(self, auth_client):
        r = auth_client.post("/api/posts", json={
            "content":"Post agendado","platforms":["twitter","linkedin"],
            "scheduled_at": future()
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data["scheduled_at"] is not None

    def test_returns_correct_fields(self, auth_client):
        r = auth_client.post("/api/posts", json={"content":"Post","platforms":["twitter"]})
        data = r.get_json()
        for key in ("id","content","status","platforms","author"):
            assert key in data, f"Campo '{key}' ausente"

    def test_ab_test_creates_two_posts(self, auth_client, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory(["twitter"])
        r = auth_client.post("/api/posts", json={
            "content":"Post A/B","platforms":["twitter"],"ab_test":True
        })
        assert r.status_code == 201
        data = r.get_json()
        assert "a" in data and "b" in data
        assert data["a"]["ab_variant"] == "A"
        assert data["b"]["ab_variant"] == "B"
        assert data["a"]["ab_group_id"] == data["b"]["ab_group_id"]

class TestListPosts:
    def test_returns_list(self, auth_client):
        r = auth_client.get("/api/posts")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_filter_by_status(self, auth_client):
        auth_client.post("/api/posts", json={"content":"Rascunho","platforms":["twitter"]})
        r = auth_client.get("/api/posts?status=draft")
        posts = r.get_json()
        assert all(p["status"] == "draft" for p in posts)

class TestApprovalWorkflow:
    def _create_editor_client(self, app, username):
        """Cria cliente autenticado como editor."""
        with app.app_context():
            from core.models import User, UserRole, db
            if not User.query.filter_by(username=username).first():
                u = User(username=username, email=f"{username}@t.com", role=UserRole.EDITOR)
                u.set_password("ed123"); db.session.add(u); db.session.commit()
        ec = app.test_client()
        ec.post("/login", data={"identifier": username, "password": "ed123"})
        return ec

    def test_submit_for_review(self, app):
        ec = self._create_editor_client(app, "ed_submit")
        post_r = ec.post("/api/posts", json={"content":"Post draft","platforms":["twitter"]})
        assert post_r.status_code == 201
        pid = post_r.get_json()["id"]
        r = ec.post(f"/api/posts/{pid}/submit")
        assert r.status_code == 200
        assert r.get_json()["status"] == "pending_review"

    def test_approve_post(self, auth_client, app):
        # Editor cria e envia
        ec = self._create_editor_client(app, "ed_approve")
        post_r = ec.post("/api/posts", json={"content":"P aprovação","platforms":["twitter"]})
        pid = post_r.get_json()["id"]
        ec.post(f"/api/posts/{pid}/submit")

        # Admin aprova (auth_client é admin)
        r = auth_client.post(f"/api/posts/{pid}/approve")
        assert r.status_code == 200
        assert r.get_json()["post"]["status"] in ("approved", "published")

    def test_reject_post(self, auth_client, app):
        ec = self._create_editor_client(app, "ed_reject")
        pid = ec.post("/api/posts", json={"content":"P","platforms":["twitter"]}).get_json()["id"]
        ec.post(f"/api/posts/{pid}/submit")

        r = auth_client.post(f"/api/posts/{pid}/reject", json={"reason":"Precisa de ajustes."})
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "rejected"
        assert "ajustes" in data["rejection_reason"]

    def test_delete_own_post(self, auth_client):
        pid = auth_client.post("/api/posts", json={"content":"Del","platforms":["twitter"]}).get_json()["id"]
        r = auth_client.delete(f"/api/posts/{pid}")
        assert r.status_code == 200

    def test_delete_nonexistent_returns_404(self, auth_client):
        assert auth_client.delete("/api/posts/999999").status_code == 404

class TestCalendar:
    def test_calendar_returns_list(self, auth_client):
        r = auth_client.get("/api/posts/calendar")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)
