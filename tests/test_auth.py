"""tests/test_auth.py — Testes de autenticação."""

class TestLoginPage:
    def test_returns_200(self, client): assert client.get("/login").status_code == 200
    def test_has_form_fields(self, client):
        html = client.get("/login").data.decode()
        assert "identifier" in html and "password" in html
    def test_has_register_link(self, client): assert b"register" in client.get("/login").data.lower()

class TestLogin:
    def test_valid_credentials_redirect(self, client):
        r = client.post("/login", data={"identifier":"admin","password":"senha123"}, follow_redirects=False)
        assert r.status_code == 302

    def test_wrong_password_shows_error(self, client):
        r = client.post("/login", data={"identifier":"admin","password":"errada"}, follow_redirects=True)
        assert "incorretos" in r.data.decode()

    def test_wrong_user_shows_error(self, client):
        r = client.post("/login", data={"identifier":"naoexiste","password":"x"}, follow_redirects=True)
        assert "incorretos" in r.data.decode()

    def test_email_login(self, client):
        r = client.post("/login", data={"identifier":"admin@test.com","password":"senha123"}, follow_redirects=False)
        assert r.status_code == 302

class TestRegister:
    def test_register_page_200(self, client): assert client.get("/register").status_code == 200

    def test_creates_user(self, client):
        r = client.post("/register", data={
            "username":"novo","email":"novo@t.com",
            "password":"abc123","password2":"abc123"
        }, follow_redirects=False)
        assert r.status_code == 302

    def test_duplicate_username_rejected(self, client):
        client.post("/register", data={"username":"dup","email":"dup@a.com","password":"abc123","password2":"abc123"})
        client.get("/logout")  # sair antes de tentar novo registro
        r = client.post("/register", data={"username":"dup","email":"dup2@a.com","password":"abc123","password2":"abc123"}, follow_redirects=True)
        assert r.status_code == 200
        assert any(word in r.data.decode() for word in ["uso", "duplicado", "existe", "already"])

    def test_short_password_rejected(self, client):
        r = client.post("/register", data={"username":"usr2pw","email":"usr2pw@t.com","password":"abc","password2":"abc"}, follow_redirects=True)
        assert r.status_code == 200
        assert any(c in r.data.decode() for c in ["6", "curta", "senha"])

    def test_password_mismatch_rejected(self, client):
        r = client.post("/register", data={"username":"u3mm","email":"u3mm@t.com","password":"abc123","password2":"xyz999"}, follow_redirects=True)
        assert r.status_code == 200
        assert any(word in r.data.decode() for word in ["coincidem", "iguais", "match"])

class TestProtectedRoutes:
    def test_dashboard_requires_auth(self, client):
        assert client.get("/", follow_redirects=False).status_code == 302

    def test_api_requires_auth(self, client):
        for path in ["/api/jobs","/api/stats","/api/log","/api/me","/api/posts","/api/templates"]:
            assert client.get(path).status_code in (302, 401), f"Path {path} deveria exigir auth"

    def test_authenticated_accesses_dashboard(self, auth_client):
        assert auth_client.get("/").status_code == 200

class TestLogout:
    def test_logout_redirects(self, auth_client):
        r = auth_client.get("/logout", follow_redirects=False)
        assert r.status_code == 302
    def test_after_logout_blocked(self, auth_client):
        auth_client.get("/logout")
        assert auth_client.get("/", follow_redirects=False).status_code == 302
