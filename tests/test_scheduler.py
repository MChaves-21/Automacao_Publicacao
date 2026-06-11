"""
tests/test_scheduler.py — Testes do módulo de agendamento.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


def _future(minutes: int = 30) -> datetime:
    return datetime.now() + timedelta(minutes=minutes)


@pytest.fixture(autouse=True)
def isolated_scheduler(tmp_path):
    """Garante scheduler limpo com banco temporário para cada teste."""
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    db = tmp_path / "sched_test.db"
    log = tmp_path / "sched_log.json"

    with patch("core.scheduler.DB_PATH", str(db)), \
         patch("core.scheduler.LOG_FILE", log), \
         patch("core.scheduler._jobstores", {
             "default": SQLAlchemyJobStore(url=f"sqlite:///{db}")
         }):
        from core import scheduler as sched_mod
        # Força criação de novo scheduler para o teste
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.executors.pool import ThreadPoolExecutor
        new_sched = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{db}")},
            executors={"default": ThreadPoolExecutor(max_workers=2)},
            job_defaults={"coalesce": True, "max_instances": 1},
            timezone="America/Sao_Paulo",
        )
        old = sched_mod.scheduler
        sched_mod.scheduler = new_sched
        new_sched.start()
        yield sched_mod
        new_sched.shutdown(wait=False)
        sched_mod.scheduler = old


class TestSchedulePost:
    def test_creates_job_and_returns_id(self, isolated_scheduler):
        job_id = isolated_scheduler.schedule_post(
            original_text="Conteúdo de teste",
            run_at=_future(60),
            platforms=["twitter"],
            label="meu-post",
        )
        assert job_id == "meu-post"

    def test_job_appears_in_list(self, isolated_scheduler):
        isolated_scheduler.schedule_post("texto", _future(60), label="list-test")
        jobs = isolated_scheduler.list_jobs()
        assert any(j["id"] == "list-test" for j in jobs)

    def test_past_date_raises_value_error(self, isolated_scheduler):
        past = datetime.now() - timedelta(hours=1)
        with pytest.raises(ValueError, match="futura"):
            isolated_scheduler.schedule_post("texto", past)

    def test_default_label_uses_datetime(self, isolated_scheduler):
        run_at = _future(45)
        job_id = isolated_scheduler.schedule_post("texto", run_at)
        assert run_at.strftime("%Y%m%d_%H%M") in job_id

    def test_replaces_existing_job_with_same_label(self, isolated_scheduler):
        isolated_scheduler.schedule_post("v1", _future(60), label="dup")
        isolated_scheduler.schedule_post("v2", _future(90), label="dup")
        jobs = isolated_scheduler.list_jobs()
        assert sum(1 for j in jobs if j["id"] == "dup") == 1

    def test_default_platforms_are_four(self, isolated_scheduler):
        isolated_scheduler.schedule_post("texto", _future(), label="plat-test")
        jobs = isolated_scheduler.list_jobs()
        job = next(j for j in jobs if j["id"] == "plat-test")
        assert len(job["platforms"]) == 4


class TestListJobs:
    def test_empty_initially(self, isolated_scheduler):
        assert isolated_scheduler.list_jobs() == []

    def test_returns_correct_structure(self, isolated_scheduler):
        isolated_scheduler.schedule_post("texto", _future(), label="struct-check")
        jobs = isolated_scheduler.list_jobs()
        job = jobs[0]
        assert "id" in job
        assert "name" in job
        assert "next_run" in job
        assert "platforms" in job

    def test_next_run_is_formatted_string(self, isolated_scheduler):
        isolated_scheduler.schedule_post("texto", _future(), label="fmt-check")
        job = isolated_scheduler.list_jobs()[0]
        # Formato esperado: DD/MM/YYYY HH:MM
        import re
        assert re.match(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", job["next_run"])


class TestCancelJob:
    def test_cancels_existing_job(self, isolated_scheduler):
        isolated_scheduler.schedule_post("texto", _future(), label="to-cancel")
        result = isolated_scheduler.cancel_job("to-cancel")
        assert result is True

    def test_removed_from_list_after_cancel(self, isolated_scheduler):
        isolated_scheduler.schedule_post("texto", _future(), label="gone")
        isolated_scheduler.cancel_job("gone")
        jobs = isolated_scheduler.list_jobs()
        assert not any(j["id"] == "gone" for j in jobs)

    def test_returns_false_for_nonexistent_job(self, isolated_scheduler):
        result = isolated_scheduler.cancel_job("nao-existe")
        assert result is False


class TestReadLog:
    def test_returns_empty_list_when_no_log(self, isolated_scheduler, tmp_path):
        entries = isolated_scheduler.read_log()
        assert entries == []

    def test_returns_entries_in_reverse_order(self, isolated_scheduler, tmp_path):
        import json
        log = isolated_scheduler.LOG_FILE
        entries = [
            {"timestamp": "2024-01-01T10:00", "label": "primeiro"},
            {"timestamp": "2024-01-01T11:00", "label": "segundo"},
        ]
        with open(log, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        result = isolated_scheduler.read_log()
        assert result[0]["label"] == "segundo"
        assert result[1]["label"] == "primeiro"

    def test_respects_limit(self, isolated_scheduler, tmp_path):
        import json
        log = isolated_scheduler.LOG_FILE
        with open(log, "w") as f:
            for i in range(20):
                f.write(json.dumps({"label": f"post-{i}"}) + "\n")

        result = isolated_scheduler.read_log(limit=5)
        assert len(result) == 5


class TestExecutePost:
    def test_calls_publisher_for_each_platform(self, isolated_scheduler):
        mock_adapted = MagicMock()
        mock_adapted.text = "texto"
        mock_publisher = MagicMock(return_value={"platform": "twitter", "id": "1"})

        with patch("core.ai_processor.adapt_content", return_value={"twitter": mock_adapted}), \
             patch("core.publishers.PUBLISHERS", {"twitter": mock_publisher}):
            isolated_scheduler._execute_post(
                original_text="texto",
                platforms=["twitter"],
                image_url=None,
                job_label="exec-test",
            )
            mock_publisher.assert_called_once()

    def test_logs_fatal_error_on_adapt_failure(self, isolated_scheduler, tmp_path):
        import json
        with patch("core.ai_processor.adapt_content", side_effect=Exception("Gemini down")):
            isolated_scheduler._execute_post(
                original_text="texto",
                platforms=["twitter"],
                image_url=None,
                job_label="fail-test",
            )
        entries = isolated_scheduler.read_log()
        assert any(e.get("fatal_error") for e in entries)
