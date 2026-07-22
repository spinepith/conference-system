from __future__ import annotations

from django.utils import timezone

from .integrations.content_validation_stage import register_content_validation_stage
from .integrations.docx_stages import register_docx_stages
from .integrations.pdf_stages import register_pdf_stages

from .models import EventLog, Submission, WorkflowStageResult
from .plugin_registry import registry
from .services import SubmissionService


class WorkflowEngine:
    """Runs registered processing stages against the latest submission state."""

    def _register_default_stages(self) -> None:
        register_docx_stages()
        register_content_validation_stage()
        register_pdf_stages()

    def _apply_stage_status(
        self,
        service: SubmissionService,
        submission_id: str,
        stage_status: str,
        result_payload: dict,
    ) -> None:
        current = service.get_submission(submission_id)["status"]

        if stage_status == "failed":
            if current != "error":
                service.update_submission_status(
                    submission_id,
                    "error",
                    result_payload.get("message", "Ошибка этапа workflow."),
                    "workflow",
                )
            return

        if stage_status not in {"success", "warning"}:
            return

        next_status = result_payload.get("next_status")
        if not next_status:
            return

        # If current status is "error", always try to update to next_status
        if current == "error":
            try:
                service.update_submission_status(
                    submission_id,
                    next_status,
                    result_payload.get("message", "Ошибка исправлена. Этап workflow завершён успешно."),
                    "workflow",
                )
            except ValueError as exc:
                service.add_event(
                    submission_id,
                    "workflow_status_unchanged",
                    {
                        "current_status": current,
                        "requested_status": next_status,
                        "reason": str(exc),
                    },
                )
            return

        if current == next_status:
            return
        try:
            service.update_submission_status(
                submission_id,
                next_status,
                result_payload.get("message", "Этап workflow завершён."),
                "workflow",
            )
        except ValueError as exc:
            # A repeated workflow run must not downgrade an already processed
            # submission. The event remains visible for diagnostics.
            service.add_event(
                submission_id,
                "workflow_status_unchanged",
                {
                    "current_status": current,
                    "requested_status": next_status,
                    "reason": str(exc),
                },
            )

    def run(self, submission_id: str) -> list[dict]:
        self._register_default_stages()
        service = SubmissionService()
        Submission.objects.get(pk=submission_id)  # explicit not-found check

        results: list[dict] = []
        for stage in registry.list():
            started_at = timezone.now()
            try:
                # Important for integration: every stage receives the state
                # saved by all previous stages, including newly created files.
                submission_dict = service.get_submission(submission_id)
                if not stage.enabled:
                    result_payload = {"status": "skipped", "message": "Этап отключён."}
                else:
                    result_payload = stage.run(submission_dict)
                status = result_payload.get("status", "success")
                if status not in {"success", "warning", "failed", "skipped"}:
                    status = "failed"
                    result_payload["status"] = status
                    result_payload.setdefault("message", "Этап вернул неизвестный статус.")
                message = result_payload.get("message", "")
            except Exception as exc:  # workflow must preserve the rest of the system
                result_payload = {"status": "failed", "message": str(exc), "error": str(exc)}
                status = "failed"
                message = str(exc)

            try:
                self._apply_stage_status(service, submission_id, status, result_payload)
            except Exception as exc:  # status bookkeeping must not hide stage result
                result_payload.setdefault("status_update_error", str(exc))

            finished_at = timezone.now()
            submission_model = Submission.objects.get(pk=submission_id)
            row = WorkflowStageResult.objects.create(
                submission=submission_model,
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
            EventLog.objects.create(
                submission=submission_model,
                event_type="workflow_stage_finished",
                payload=event_payload,
            )
            results.append({**event_payload, "result": result_payload})
        return results
