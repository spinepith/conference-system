from __future__ import annotations

from conference_system.app.database import SessionLocal, init_db
from conference_system.submissions.service import SubmissionService


def sample_data():
    return {
        "conference_id": "ai_quarterly_conf",
        "issue_id": "2026_q1",
        "author_contact": {
            "full_name": "Иванов Иван Иванович",
            "email": "ivanov@example.com",
            "organization": "ТГТУ",
        },
        "metadata": {
            "title_ru": "Тестовый материал",
            "authors": [{"full_name": "Иванов И.И.", "organization": "ТГТУ", "email": "ivanov@example.com"}],
            "section": "ИИ в образовании",
            "keywords_ru": ["ИИ", "тест"],
            "abstract_ru": "Аннотация",
        },
    }


def test_create_and_get_submission():
    init_db()
    with SessionLocal() as db:
        service = SubmissionService(db)
        created = service.create_submission(sample_data())
        assert created["submission_id"].startswith("SUB-2026-Q1-")
        assert created["status"] == "draft"
        loaded = service.get_submission(created["submission_id"])
        assert loaded["metadata"]["title_ru"] == "Тестовый материал"
        assert len(loaded["status_history"]) == 1


def test_update_status_and_history():
    init_db()
    with SessionLocal() as db:
        service = SubmissionService(db)
        created = service.create_submission(sample_data())
        updated = service.update_submission_status(created["submission_id"], "uploaded", "Файл загружен", "author")
        assert updated["status"] == "uploaded"
        assert len(updated["status_history"]) == 2
        assert updated["status_history"][-1]["to_status"] == "uploaded"


def test_save_check_result():
    init_db()
    with SessionLocal() as db:
        service = SubmissionService(db)
        created = service.create_submission(sample_data())
        service.save_check_result(
            created["submission_id"],
            {
                "check_id": "formal_structure_check",
                "title": "Формальная проверка",
                "status": "warning",
                "risk_level": "low",
                "summary": "Есть замечания",
                "warnings": [],
                "errors": [],
            },
        )
        loaded = service.get_submission(created["submission_id"])
        assert len(loaded["checks"]) == 1
        assert "check_report" in loaded["files"]
