from __future__ import annotations

from django.utils import timezone

from .demo_stages import register_demo_stages
from .models import EventLog, Submission, WorkflowStageResult
from .plugin_registry import registry
from .services import SubmissionService


class WorkflowEngine:
    def run(self, submission_id: str) -> list[dict]:
        register_demo_stages()
        service = SubmissionService()
        submission = Submission.objects.prefetch_related("files", "checks").get(pk=submission_id)
        submission_dict = service.to_dict(submission)
        results: list[dict] = []
        for stage in registry.list():
            started_at = timezone.now()
            try:
                if not stage.enabled:
                    result_payload = {"status": "skipped", "message": "Этап отключён."}
                else:
                    result_payload = stage.run(submission_dict)
                status = result_payload.get("status", "success")
                message = result_payload.get("message", "")
            except Exception as exc:  # noqa: BLE001 - workflow should not crash the whole system
                result_payload = {"status": "failed", "message": str(exc), "error": str(exc)}
                status = "failed"
                message = str(exc)
            finished_at = timezone.now()
            row = WorkflowStageResult.objects.create(
                submission=submission,
                stage_id=stage.stage_id,
                title=stage.title,
                status=status,
                message=message,
                result_json=result_payload,
                started_at=started_at,
                finished_at=finished_at,
            )
            event_payload = {
                "stage_id": row.stage_id,
                "title": row.title,
                "status": row.status,
                "message": row.message,
            }
            EventLog.objects.create(submission=submission, event_type="workflow_stage_finished", payload=event_payload)
            results.append(event_payload)
        return results
