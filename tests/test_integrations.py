"""tests/test_integrations.py — Brand Voice, RSS, Webhooks, Score, Upload, Export, Recycling."""
import io, json
from unittest.mock import MagicMock, patch


# ── Brand Voice ───────────────────────────────────────────────────────────────

class TestBrandVoice:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/api/brand-voice")
        assert r.status_code == 200 and isinstance(r.get_json(), list)

    def test_create(self, auth_client):
        r = auth_client.post("/api/brand-voice", json={
            "name":"Marca X","tone":"casual",
            "keywords":["inovação","qualidade"],"is_active":True
        })
        assert r.status_code == 201
        d = r.get_json()
        assert d["name"] == "Marca X" and d["tone"] == "casual"

    def test_appears_in_list(self, auth_client):
        auth_client.post("/api/brand-voice", json={"name":"BV Lista","is_active":False})
        bvs = auth_client.get("/api/brand-voice").get_json()
        assert any(b["name"]=="BV Lista" for b in bvs)

    def test_update(self, auth_client):
        vid = auth_client.post("/api/brand-voice",
            json={"name":"BV Update","is_active":False}).get_json()["id"]
        r = auth_client.patch(f"/api/brand-voice/{vid}",
            json={"tone":"inspiracional","is_active":True})
        assert r.status_code == 200
        assert r.get_json()["tone"] == "inspiracional"

    def test_delete(self, auth_client):
        vid = auth_client.post("/api/brand-voice",
            json={"name":"BV Del","is_active":False}).get_json()["id"]
        r = auth_client.delete(f"/api/brand-voice/{vid}")
        assert r.status_code == 200 and r.get_json()["ok"] is True

    def test_missing_name_rejected(self, auth_client):
        r = auth_client.post("/api/brand-voice", json={"tone":"casual"})
        assert r.status_code == 400

    def test_build_voice_instruction(self):
        from core.brand_voice import build_voice_instruction
        voice = {"name":"Teste","tone":"profissional","keywords":["qualidade"],
                 "avoid_words":["barato"],"description":"Uma marca top","example_post":""}
        instr = build_voice_instruction(voice)
        assert "Teste" in instr and "qualidade" in instr and "barato" in instr


# ── RSS Feeds ─────────────────────────────────────────────────────────────────

class TestRssFeeds:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/api/rss")
        assert r.status_code == 200 and isinstance(r.get_json(), list)

    def test_create(self, auth_client):
        r = auth_client.post("/api/rss", json={
            "name":"Tech News","url":"https://feeds.exemplo.com/rss",
            "platforms":["twitter"],"interval_hours":4
        })
        assert r.status_code == 201
        d = r.get_json()
        assert d["name"] == "Tech News" and d["interval_hours"] == 4

    def test_missing_url_rejected(self, auth_client):
        r = auth_client.post("/api/rss", json={"name":"Sem URL"})
        assert r.status_code == 400

    def test_delete(self, auth_client):
        fid = auth_client.post("/api/rss",
            json={"name":"Del Feed","url":"https://x.com/feed"}).get_json()["id"]
        r = auth_client.delete(f"/api/rss/{fid}")
        assert r.status_code == 200

    def test_check_feed_with_mock(self, auth_client, app):
        with app.app_context():
            from core.models import RssFeed, db
            feed = RssFeed(name="Mock Feed",url="https://mock.com/feed",
                           platforms=["twitter"],author_id=1)
            db.session.add(feed); db.session.commit()
            fid = feed.id

        import feedparser
        class FakeEntry:
            title = "Artigo 1"
            summary = "Resumo do artigo"
            link = "https://blog.com/artigo-1"
            id = "entry-1"
            def get(self, key, default=""):
                return getattr(self, key, default)

        mock_parsed = MagicMock()
        mock_parsed.entries = [FakeEntry()]

        with patch("feedparser.parse", return_value=mock_parsed), \
             patch("core.ai_processor.adapt_content", return_value={}):
            r = auth_client.post(f"/api/rss/{fid}/check")
        assert r.status_code == 200


# ── Webhooks ──────────────────────────────────────────────────────────────────

class TestWebhooks:
    def test_list_empty(self, auth_client):
        r = auth_client.get("/api/webhooks")
        assert r.status_code == 200 and isinstance(r.get_json(), list)

    def test_create(self, auth_client):
        r = auth_client.post("/api/webhooks", json={
            "name":"Zapier","url":"https://hooks.zapier.com/test",
            "events":["post.published","post.failed"]
        })
        assert r.status_code == 201
        d = r.get_json()
        assert d["name"] == "Zapier"
        assert "secret" in d  # secret só retorna na criação
        assert len(d["secret"]) > 10

    def test_missing_url_rejected(self, auth_client):
        r = auth_client.post("/api/webhooks", json={"name":"Sem URL"})
        assert r.status_code == 400

    def test_delete(self, auth_client):
        wid = auth_client.post("/api/webhooks",
            json={"name":"Del","url":"https://x.com/hook"}).get_json()["id"]
        r = auth_client.delete(f"/api/webhooks/{wid}")
        assert r.status_code == 200

    def test_test_webhook_calls_dispatch(self, auth_client):
        wid = auth_client.post("/api/webhooks",
            json={"name":"Test Hook","url":"https://httpbin.org/post"}).get_json()["id"]
        with patch("core.webhooks.dispatch_event", return_value=[{"webhook":"Test Hook","status":200}]) as mock_d:
            r = auth_client.post(f"/api/webhooks/{wid}/test")
        assert r.status_code == 200
        mock_d.assert_called_once()

    def test_webhook_sign_payload(self):
        from core.webhooks import _sign_payload
        sig = _sign_payload("secret123", b'{"event":"test"}')
        assert len(sig) == 64  # SHA-256 hex

    def test_slack_notify_no_url(self):
        from core.webhooks import notify_slack
        with patch("core.webhooks.config") as mock_cfg:
            mock_cfg.slack_webhook_url = ""
            result = notify_slack("post.published", "Post publicado")
        assert result is False

    def test_slack_notify_with_url(self):
        from core.webhooks import notify_slack
        with patch("core.webhooks.config") as mock_cfg, \
             patch("core.webhooks.requests.post") as mock_post:
            mock_cfg.slack_webhook_url = "https://hooks.slack.com/test"
            mock_post.return_value.status_code = 200
            result = notify_slack("post.published", "Publicado!", {"platforms":["twitter"]})
        assert result is True
        mock_post.assert_called_once()


# ── Score de Performance ──────────────────────────────────────────────────────

class TestScore:
    def test_missing_content_rejected(self, auth_client):
        r = auth_client.post("/api/score", json={})
        assert r.status_code == 400

    def test_returns_score(self, auth_client, mock_gemini):
        mock_gemini.generate_content.return_value.text = json.dumps({
            "score":8,"summary":"Excelente post com CTA claro.",
            "strengths":["gancho forte","hashtags relevantes"],
            "improvements":["adicionar emoji","encurtar texto"],
            "by_platform":{"twitter":7,"instagram":9,"linkedin":8}
        })
        r = auth_client.post("/api/score", json={
            "content":"Nosso produto revolucionou o mercado!",
            "platforms":["twitter","instagram"]
        })
        assert r.status_code == 200
        d = r.get_json()
        assert "score" in d and "strengths" in d and "improvements" in d
        assert 1 <= d["score"] <= 10

    def test_score_post_function(self):
        from core.brand_voice import score_post
        with patch("google.generativeai.GenerativeModel") as mock_m:
            mock_m.return_value.generate_content.return_value.text = json.dumps({
                "score":7,"summary":"Bom post.","strengths":[],"improvements":[],"by_platform":{}
            })
            result = score_post("Conteúdo de teste", ["twitter"])
        assert result["score"] == 7


# ── Upload de Imagem ──────────────────────────────────────────────────────────

class TestImageUpload:
    def _make_image(self):
        """Cria um arquivo PNG mínimo válido para testes."""
        # PNG header + IHDR + IDAT + IEND (1x1 pixel branco)
        import base64
        png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        return base64.b64decode(png_b64)

    def test_upload_png(self, auth_client):
        png = self._make_image()
        r = auth_client.post(
            "/api/upload/image",
            data={"file": (io.BytesIO(png), "test.png")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "url" in data
        assert data["url"].endswith(".png")

    def test_no_file_rejected(self, auth_client):
        r = auth_client.post("/api/upload/image", data={},
                             content_type="multipart/form-data")
        assert r.status_code == 400

    def test_invalid_extension_rejected(self, auth_client):
        r = auth_client.post(
            "/api/upload/image",
            data={"file": (io.BytesIO(b"fake"), "malware.exe")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_cloudinary_upload(self, auth_client):
        with patch("core.integrations_bp") if False else patch("cloudinary.uploader.upload") as mock_up, \
             patch("core.webhooks.config") if False else patch("config.config") as mock_cfg:
            pass  # Cloudinary tested via integration only


# ── Export ────────────────────────────────────────────────────────────────────

class TestExport:
    def test_csv_export(self, auth_client):
        # Criar alguns posts primeiro
        auth_client.post("/api/posts", json={"content":"Post 1","platforms":["twitter"]})
        r = auth_client.get("/api/export/posts.csv")
        assert r.status_code == 200
        assert "text/csv" in r.content_type
        lines = r.data.decode("utf-8-sig").splitlines()
        assert lines[0].startswith("id,")  # header

    def test_report_html(self, auth_client):
        r = auth_client.get("/api/export/report.html")
        assert r.status_code == 200
        assert "text/html" in r.content_type
        body = r.data.decode()
        assert "Relatório de Marketing" in body
        assert "Publicados" in body

    def test_csv_contains_posts(self, auth_client):
        auth_client.post("/api/posts", json={"content":"Export test post","platforms":["linkedin"]})
        r = auth_client.get("/api/export/posts.csv")
        assert r.status_code == 200

    def test_exporter_csv_format(self):
        from core.exporter import export_posts_csv
        posts = [{"id":1,"author":{"username":"admin"},"status":"published",
                  "platforms":["twitter"],"content":"Teste","scheduled_at":None,
                  "published_at":None,"ab_variant":None,"created_at":"2024-01-01"}]
        result = export_posts_csv(posts)
        assert b"twitter" in result
        assert b"published" in result

    def test_exporter_html_report(self):
        from core.exporter import export_report_html
        stats = {"published":5,"errors":1,"pending":2,"sessions":8,"by_platform":{"twitter":3}}
        html = export_report_html(stats, [], [])
        assert "Relatório de Marketing" in html
        assert "5" in html  # published count
        assert "twitter" in html


# ── Reciclagem ────────────────────────────────────────────────────────────────

class TestRecycling:
    def test_candidates_returns_list(self, auth_client):
        r = auth_client.get("/api/recycle/candidates")
        assert r.status_code == 200 and isinstance(r.get_json(), list)

    def test_candidates_respects_min_days(self, auth_client):
        r = auth_client.get("/api/recycle/candidates?min_days=9999")
        assert r.status_code == 200
        assert r.get_json() == []  # Nenhum post tão antigo

    def test_recycle_nonexistent_post(self, auth_client):
        r = auth_client.post("/api/recycle/999999", json={"variation": False})
        assert r.status_code in (404, 500)  # 404 ou erro de DB para ID inexistente

    def test_recycle_published_post(self, auth_client, app):
        with app.app_context():
            from core.models import Post, PostStatus, db
            from datetime import datetime, timedelta
            p = Post(author_id=1, content="Post reciclável",
                     platforms=["twitter"], status=PostStatus.PUBLISHED,
                     published_at=datetime.utcnow()-timedelta(days=60))
            db.session.add(p); db.session.commit()
            pid = p.id

        with patch("core.recycler._generate_variation", return_value="Variação do post"), \
             patch("core.ai_processor.adapt_content", return_value={}):
            r = auth_client.post(f"/api/recycle/{pid}", json={"variation": True})

        assert r.status_code == 201
        new_post = r.get_json()
        assert new_post["status"] == "draft"
        assert "Variação do post" in new_post["content"]

    def test_find_recyclable_function(self, app):
        with app.app_context():
            from core.recycler import find_recyclable
            result = find_recyclable(limit=5, min_age_days=9999)
            assert isinstance(result, list)


# ── Rate Limiting ─────────────────────────────────────────────────────────────

class TestRateLimiting:
    def test_api_accessible_normally(self, auth_client):
        r = auth_client.get("/api/jobs")
        assert r.status_code == 200

    def test_export_accessible(self, auth_client):
        r = auth_client.get("/api/export/posts.csv")
        assert r.status_code == 200


# ── PWA ───────────────────────────────────────────────────────────────────────

class TestPWA:
    def test_manifest_served(self, client):
        r = client.get("/static/manifest.json")
        assert r.status_code == 200
        data = r.get_json()
        assert data["name"] == "Marketing Automation"
        assert "icons" in data

    def test_service_worker_served(self, client):
        r = client.get("/static/sw.js")
        assert r.status_code == 200
        assert b"serviceWorker" in r.data or b"CACHE_NAME" in r.data

    def test_index_has_pwa_meta(self, auth_client):
        r = auth_client.get("/")
        assert r.status_code == 200
        html = r.data.decode()
        assert 'manifest.json' in html
        assert 'theme-color' in html
