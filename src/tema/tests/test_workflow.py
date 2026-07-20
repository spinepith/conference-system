from __future__ import annotations

from conference_system.app.database import SessionLocal, init_db
from conference_system.core.base_stage import BaseWorkflowStage
from conference_system.core.plugin_registry import registry
from conference_system.core.workflow import WorkflowEngine
from conference_system.submissions.service import SubmissionService


class TestStage(BaseWorkflowStage):
    stage_id = "test_stage"
    title = "Тестовый этап"
    description = "Проверяет workflow."

    def run(self, submission):
        return {"status": "success", "message": f"ok {submission['submission_id']}"}


def sample_data():
    return {
        "conference_id": "ai_quarterly_conf",
        "issue_id": "2026_q1",
        "author_contact": {
            "full_name": "Иванов Иван Иванович",
            "email": "ivanov@example.com",
            "organization": "ТГТУ",
        },
        "metadata": {"title_ru": "Тест", "authors": []},
    }


def test_workflow_registry_and_engine():
    init_db()
    registry.clear()
    registry.register(TestStage())
    with SessionLocal() as db:
        service = SubmissionService(db)
        created = service.create_submission(sample_data())
    results = WorkflowEngine().run_submission(created["submission_id"])
    assert results[0]["stage_id"] == "test_stage"
    assert results[0]["status"] == "success"
    with SessionLocal() as db:
        loaded = SubmissionService(db).get_submission(created["submission_id"])
        assert len(loaded["workflow_results"]) == 1
