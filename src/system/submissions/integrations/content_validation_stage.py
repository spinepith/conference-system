from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from submissions.base_stage import BaseWorkflowStage
from submissions.plugin_registry import registry
from submissions.services import (
    SubmissionService,
    project_path_reference,
    resolve_stored_file_path,
)

FILE_TYPE_EXTRACTED_METADATA = "extracted_metadata"
FILE_TYPE_CHECK_REPORT = "check_report"


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
            if not isinstance(data, dict):
                raise RuntimeError("ContentValidation API вернул ответ неизвестного формата.")
            return data
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
            message = data.get("message") or data.get("error") or body
        except json.JSONDecodeError:
            message = body or str(exc)
        raise RuntimeError(f"ContentValidation API: HTTP {exc.code}: {message}") from exc
    except URLError as exc:
        raise RuntimeError(
            "ContentValidation API недоступен. Проверьте, что windows_start.bat "
            "запустил сервис на порту 5100."
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("ContentValidation API вернул некорректный JSON.") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Не удалось прочитать результат проверки: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Ожидался JSON-объект в файле: {path}")
    return payload


class ContentValidationStage(BaseWorkflowStage):
    stage_id = "content_validation"
    title = "Автоматическая проверка содержания"
    description = "Запускает шесть проверок через ContentValidation.Api."
    enabled = True

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        if not settings.CONTENT_VALIDATION_ENABLED:
            return {
                "status": "skipped",
                "message": "ContentValidation отключён переменной CONTENT_VALIDATION_ENABLED.",
            }

        submission_id = submission["submission_id"]
        files = submission.get("files") or {}
        metadata_reference = files.get(FILE_TYPE_EXTRACTED_METADATA)
        if not metadata_reference:
            return {
                "status": "skipped" if submission.get("status") == "error" else "failed",
                "message": "Проверка содержания пропущена: extracted_metadata.json не найден.",
            }

        metadata_path = resolve_stored_file_path(metadata_reference)
        if not metadata_path.is_file():
            return {
                "status": "failed",
                "message": f"Файл метаданных отсутствует: {metadata_reference}",
                "next_status": "error",
            }

        service = SubmissionService()
        try:
            current_status = service.get_submission(submission_id)["status"]
            if current_status == "formatted":
                service.update_submission_status(
                    submission_id,
                    "auto_checking",
                    "Запущены автоматические проверки ContentValidation.",
                    "workflow",
                )
        except ValueError as exc:
            service.add_event(
                submission_id,
                "content_validation_status_unchanged",
                {"reason": str(exc)},
            )

        response = _post_json(
            f"{settings.CONTENT_VALIDATION_API_URL}/validate",
            {"submissionId": submission_id},
            settings.CONTENT_VALIDATION_TIMEOUT,
        )
        if response.get("status") != "success":
            raise RuntimeError(response.get("message") or "ContentValidation завершился с ошибкой.")

        submission_dir = metadata_path.parent
        final_path = submission_dir / "check_result.json"
        if not final_path.is_file():
            raise RuntimeError("ContentValidation не создал check_result.json.")

        final_result = _read_json(final_path)
        final_checks = final_result.get("checks") or []
        if not isinstance(final_checks, list) or not final_checks:
            raise RuntimeError("Итоговый отчёт ContentValidation не содержит результатов проверок.")

        checks_dir = submission_dir / "checks"
        imported_checks: list[dict[str, Any]] = []
        for summary in final_checks:
            if not isinstance(summary, dict) or not summary.get("check_id"):
                continue
            check_id = str(summary["check_id"])
            check_path = checks_dir / f"{check_id}.json"
            check = _read_json(check_path) if check_path.is_file() else dict(summary)
            check["raw_model_response_path"] = (
                project_path_reference(check_path) if check_path.is_file() else ""
            )
            service.save_check_result(
                submission_id,
                check,
                replace_existing=True,
            )
            imported_checks.append(
                {
                    "check_id": check.get("check_id"),
                    "status": check.get("status"),
                    "risk_level": check.get("risk_level"),
                }
            )

        report_file = service.save_or_update_file_path(
            submission_id,
            FILE_TYPE_CHECK_REPORT,
            str(final_path),
        )
        service.add_event(
            submission_id,
            "content_validation_finished",
            {
                "overall_status": final_result.get("overall_status"),
                "overall_risk_level": final_result.get("overall_risk_level"),
                "checks_count": len(imported_checks),
                "report_path": report_file["path"],
            },
        )

        has_system_error = any(
            check.get("check_id") == "system_error" or check.get("status") == "error"
            for check in imported_checks
        )
        if has_system_error:
            return {
                "status": "failed",
                "message": "ContentValidation завершился технической ошибкой. Требуется ручная проверка.",
                "report_file": report_file["path"],
                "checks": imported_checks,
                "next_status": "error",
            }

        overall_status = str(final_result.get("overall_status") or "needs_attention")
        stage_status = "success" if overall_status == "passed" else "warning"
        message = (
            "Автоматические проверки успешно пройдены. Материал передан автору на согласование."
            if overall_status == "passed"
            else "Автоматические проверки завершены с замечаниями. Материал передан автору на согласование."
        )
        return {
            "status": stage_status,
            "message": message,
            "overall_status": overall_status,
            "overall_risk_level": final_result.get("overall_risk_level", "medium"),
            "author_message": final_result.get("author_message", ""),
            "editor_message": final_result.get("editor_message", ""),
            "report_file": report_file["path"],
            "checks": imported_checks,
            "next_status": "needs_author_review",
        }


def register_content_validation_stage() -> None:
    if ContentValidationStage.stage_id not in {stage.stage_id for stage in registry.list()}:
        registry.register(ContentValidationStage())
