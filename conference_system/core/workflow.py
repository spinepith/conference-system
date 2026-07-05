from __future__ import annotations

from datetime import datetime
from typing import Any

from conference_system.app.database import SessionLocal
from conference_system.core.event_log import add_event
from conference_system.core.models import WorkflowStageResult
from conference_system.core.plugin_registry import registry
from conference_system.submissions.service import SubmissionService


class WorkflowEngine:
    """Runs registered workflow stages for a submission."""

    def __init__(self, stage_ids: list[str] | None = None) -> None:
        self.stage_ids = stage_ids

    def run_submission(self, submission_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        with SessionLocal() as db:
            service = SubmissionService(db)
            submission = service.get_submission(submission_id)
            stages = registry.list()
            if self.stage_ids is not None:
                stages = [registry.get(stage_id) for stage_id in self.stage_ids]

            for stage in stages:
                if not stage.enabled:
                    result = {
                        "stage_id": stage.stage_id,
                        "title": stage.title,
                        "status": "skipped",
                        "message": "Stage disabled",
                    }
                else:
                    started = datetime.utcnow()
                    try:
                        payload = stage.run(submission)
                        result = {
                            "stage_id": stage.stage_id,
                            "title": stage.title,
                            "status": payload.get("status", "success"),
                            "message": payload.get("message", ""),
                            "result": payload,
                            "started_at": started,
                            "finished_at": datetime.utcnow(),
                        }
                    except Exception as exc:  # noqa: BLE001 - workflow must not crash the system
                        result = {
                            "stage_id": stage.stage_id,
                            "title": stage.title,
                            "status": "failed",
                            "message": str(exc),
                            "result": {"error": str(exc)},
                            "started_at": started,
                            "finished_at": datetime.utcnow(),
                        }

                serializable_result = {
                    "stage_id": result["stage_id"],
                    "title": result.get("title", ""),
                    "status": result.get("status", "failed"),
                    "message": result.get("message", ""),
                    "result": result.get("result", result),
                    "started_at": result.get("started_at", datetime.utcnow()).isoformat(),
                    "finished_at": result.get("finished_at", datetime.utcnow()).isoformat(),
                }
                stage_result = WorkflowStageResult(
                    submission_id=submission_id,
                    stage_id=serializable_result["stage_id"],
                    title=serializable_result.get("title", ""),
                    status=serializable_result.get("status", "failed"),
                    message=serializable_result.get("message", ""),
                    result_json=serializable_result.get("result", serializable_result),
                    started_at=result.get("started_at", datetime.utcnow()),
                    finished_at=result.get("finished_at", datetime.utcnow()),
                )
                db.add(stage_result)
                add_event(db, submission_id, "workflow_stage_finished", serializable_result)
                db.commit()
                results.append(serializable_result)
        return results
