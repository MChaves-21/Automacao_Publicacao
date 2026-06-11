"""
tests/test_api.py — Testes dos endpoints REST.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


def future_dt(minutes: int = 60) -> str:
    dt = datetime.now() + timedelta(minutes=minutes)
    return dt.strftime("%Y-%m-%dT%H:%M")


# ── /api/jobs GET ─────────────────────────────────────────────────────────────

class TestGetJobs:
    def test_returns_list(self, auth_client):
        res = auth_client.get("/api/jobs")
        assert res.status_code == 200
        assert isinstance(res.get_json(), list)

    def test_returns_list_type(self, auth_client):
        res = auth_client.get("/api/jobs")
        assert isinstance(res.get_json(), list)


# ── /api/jobs POST ────────────────────────────────────────────────────────────

class TestCreateJob:
    def test_creates_job_successfully(self, auth_client):
        payload = {
            "text": "Lançamento do novo produto! 🚀",
            "run_at": future_dt(120),
            "platforms": ["twitter", "linkedin"],
        }
        res = auth_client.post("/api/jobs", json=payload)
        assert res.status_code == 201
        data = res.get_json()
        assert "id" in data
        assert "run_at" in data

    def test_job_appears_in_list(self, auth_client):
        auth_client.post("/api/jobs", json={
            "text": "Post de teste",
            "run_at": future_dt(90),
            "platforms": ["twitter"],
            "label": "test-job-list",
        })
        res = auth_client.get("/api/jobs")
        jobs = res.get_json()
        assert any(j["id"] == "test-job-list" for j in jobs)

    def test_missing_text_returns_400(self, auth_client):
        res = auth_client.post("/api/jobs", json={"run_at": future_dt()})
        assert res.status_code == 400
        assert "text" in res.get_json()["error"].lower()

    def test_missing_run_at_returns_400(self, auth_client):
        res = auth_client.post("/api/jobs", json={"text": "post"})
        assert res.status_code == 400

    def test_past_date_returns_400(self, auth_client):
        past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        res = auth_client.post("/api/jobs", json={"text": "post", "run_at": past})
        assert res.status_code == 400

    def test_invalid_date_format_returns_400(self, auth_client):
        res = auth_client.post("/api/jobs", json={
            "text": "post", "run_at": "25/12/2099 10:00"
        })
        assert res.status_code == 400

    def test_defaults_to_all_platforms(self, auth_client):
        res = auth_client.post("/api/jobs", json={
            "text": "post sem plataformas",
            "run_at": future_dt(),
            "label": "test-default-platforms",
        })
        assert res.status_code == 201
        jobs = auth_client.get("/api/jobs").get_json()
        job = next((j for j in jobs if j["id"] == "test-default-platforms"), None)
        assert job is not None
        assert len(job["platforms"]) == 4


# ── /api/jobs/<id> DELETE ─────────────────────────────────────────────────────

class TestDeleteJob:
    def test_cancels_existing_job(self, auth_client):
        auth_client.post("/api/jobs", json={
            "text": "post para cancelar",
            "run_at": future_dt(),
            "label": "cancel-me",
        })
        res = auth_client.delete("/api/jobs/cancel-me")
        assert res.status_code == 200
        assert res.get_json()["ok"] is True

    def test_job_removed_from_list_after_cancel(self, auth_client):
        auth_client.post("/api/jobs", json={
            "text": "post",
            "run_at": future_dt(),
            "label": "remove-check",
        })
        auth_client.delete("/api/jobs/remove-check")
        jobs = auth_client.get("/api/jobs").get_json()
        assert not any(j["id"] == "remove-check" for j in jobs)

    def test_cancel_nonexistent_returns_404(self, auth_client):
        res = auth_client.delete("/api/jobs/nao-existe-xyz")
        assert res.status_code == 404


# ── /api/preview POST ─────────────────────────────────────────────────────────

class TestPreview:
    def test_returns_adapted_content(self, auth_client, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory()
        res = auth_client.post("/api/preview", json={
            "text": "Conteúdo para testar o preview",
            "platforms": ["twitter", "linkedin"],
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "twitter" in data
        assert "text" in data["twitter"]
        assert "hashtags" in data["twitter"]
        assert "char_count" in data["twitter"]

    def test_missing_text_returns_400(self, auth_client):
        res = auth_client.post("/api/preview", json={})
        assert res.status_code == 400

    def test_gemini_error_returns_500(self, auth_client):
        with patch("core.ai_processor.adapt_content", side_effect=Exception("Gemini offline")):
            res = auth_client.post("/api/preview", json={"text": "post"})
            assert res.status_code == 500


# ── /api/publish POST ─────────────────────────────────────────────────────────

class TestPublishNow:
    def test_missing_text_returns_400(self, auth_client):
        res = auth_client.post("/api/publish", json={})
        assert res.status_code == 400

    def test_returns_results_and_errors_keys(self, auth_client, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory()
        mock_publisher = MagicMock(return_value={"platform": "twitter", "id": "123"})
        with patch("core.publishers.PUBLISHERS", {"twitter": mock_publisher}):
            res = auth_client.post("/api/publish", json={
                "text": "post imediato",
                "platforms": ["twitter"],
            })
        assert res.status_code == 200
        data = res.get_json()
        assert "results" in data
        assert "errors" in data

    def test_publisher_exception_goes_to_errors(self, auth_client, mock_gemini, gemini_response_factory):
        mock_gemini.generate_content.return_value.text = gemini_response_factory()
        mock_publisher = MagicMock(side_effect=Exception("API down"))
        with patch("core.publishers.PUBLISHERS", {"twitter": mock_publisher}):
            res = auth_client.post("/api/publish", json={
                "text": "post",
                "platforms": ["twitter"],
            })
        data = res.get_json()
        assert len(data["errors"]) == 1
        assert data["errors"][0]["platform"] == "twitter"


# ── /api/stats GET ────────────────────────────────────────────────────────────

class TestStats:
    def test_returns_expected_keys(self, auth_client):
        res = auth_client.get("/api/stats")
        assert res.status_code == 200
        data = res.get_json()
        for key in ("scheduled", "published", "errors", "sessions", "by_platform"):
            assert key in data, f"Chave '{key}' ausente no retorno de /api/stats"

    def test_scheduled_count_matches_jobs(self, auth_client):
        # Cria 2 jobs
        for i in range(2):
            auth_client.post("/api/jobs", json={
                "text": f"post {i}",
                "run_at": future_dt(60 + i * 10),
                "label": f"stats-job-{i}",
            })
        stats = auth_client.get("/api/stats").get_json()
        assert stats["scheduled"] >= 2


# ── /api/log GET ──────────────────────────────────────────────────────────────

class TestLog:
    def test_returns_list(self, auth_client):
        res = auth_client.get("/api/log")
        assert res.status_code == 200
        assert isinstance(res.get_json(), list)
