"""Integration adapter between the Django core and external DOCX module.

The student-2 package remains independent and lives outside ``system``.
This file is the only layer that knows both the Django core contracts and
``docx_processing.service``.
"""
from __future__ import annotations

from importlib import import_module
import json
from pathlib import Path
from typing import Any, Callable

from django.conf import settings

from submissions.base_stage import BaseWorkflowStage
from submissions.services import SubmissionService, resolve_stored_file_path

FILE_TYPE_ORIGINAL_DOCX = "original_docx"
FILE_TYPE_REVISION_DOCX = "revision_docx"
FILE_TYPE_EXTRACTED_METADATA = "extracted_metadata"
FILE_TYPE_FORMATTED_DOCX = "formatted_docx"
FILE_TYPE_FORMATTING_REPORT = "formatting_report"


def _load_docx_service_functions() -> tuple[Callable, Callable, Callable, Callable]:
    """Load the external module lazily and provide a readable configuration error."""
    try:
        service_module = import_module("docx_processing.service")
    except ModuleNotFoundError as exc:
        configured_path = getattr(settings, "DOCX_PROCESSING_ROOT", "не задан")
        raise RuntimeError(
            "Модуль docx_processing не найден. Проверьте PATH_MODULE_DOCX_PROCESSING "
            f"в корневом .env. Текущее значение: {configured_path}"
        ) from exc

    return (
        service_module.extract_metadata,
        service_module.format_to_template,
        service_module.load_extracted_metadata,
        service_module.save_extracted_metadata,
    )


def _submission_output_dir(submission_id: str) -> Path:
    path = Path(settings.SUBMISSIONS_STORAGE_DIR) / submission_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_status(status: str) -> str:
    if status == "partial":
        return "warning"
    if status in {"success", "warning", "failed", "skipped"}:
        return status
    return "failed"


def _critical_extraction_failure(metadata: dict[str, Any]) -> bool:
    warnings = [str(item).casefold() for item in metadata.get("warnings", [])]
    fatal_markers = (
        "файл не найден",
        "ошибка чтения docx",
        "непредвиденная ошибка извлечения",
    )
    if any(marker in warning for warning in warnings for marker in fatal_markers):
        return True
    return not any(
        [
            metadata.get("title"),
            metadata.get("body_text"),
            metadata.get("authors"),
            metadata.get("abstract"),
            metadata.get("references"),
        ]
    )


class ExtractMetadataStage(BaseWorkflowStage):
    stage_id = "extract_metadata"
    title = "Извлечение структуры материала"
    description = "Извлекает метаданные и структуру из исходного DOCX."
    enabled = True

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        extract_metadata, _, _, save_extracted_metadata = _load_docx_service_functions()
        service = SubmissionService()
        submission_id = submission["submission_id"]
        files = submission.get("files") or {}
        source_value = files.get(FILE_TYPE_REVISION_DOCX) or files.get(FILE_TYPE_ORIGINAL_DOCX)
        if not source_value:
            return {
                "status": "failed",
                "message": "В заявке отсутствует исходный DOCX-файл.",
                "next_status": "error",
            }

        source_path = resolve_stored_file_path(source_value)
        if not source_path.exists():
            return {
                "status": "failed",
                "message": f"Исходный DOCX не найден: {source_value}",
                "next_status": "error",
            }

        output_dir = _submission_output_dir(submission_id)
        metadata_path = output_dir / "extracted_metadata.json"
        metadata = extract_metadata(
            str(source_path),
            submission_id=submission_id,
            storage_dir=str(settings.SUBMISSIONS_STORAGE_DIR),
        )

        if not save_extracted_metadata(metadata, str(metadata_path)):
            return {
                "status": "failed",
                "message": "Не удалось сохранить extracted_metadata.json.",
                "warnings": metadata.get("warnings", []),
                "next_status": "error",
            }

        service.merge_extracted_metadata(submission_id, metadata)
        saved_file = service.save_or_update_file_path(
            submission_id,
            FILE_TYPE_EXTRACTED_METADATA,
            str(metadata_path),
        )

        warnings = metadata.get("warnings", []) or []
        if _critical_extraction_failure(metadata):
            return {
                "status": "failed",
                "message": "DOCX не удалось распознать. Подробности сохранены в отчёте извлечения.",
                "warnings": warnings,
                "metadata_file": saved_file["path"],
                "next_status": "error",
            }

        status = "warning" if warnings else "success"
        return {
            "status": status,
            "message": (
                "Структура DOCX извлечена с предупреждениями."
                if warnings
                else "Структура DOCX успешно извлечена."
            ),
            "metadata_file": saved_file["path"],
            "summary": {
                "title": metadata.get("title", ""),
                "authors_count": len(metadata.get("authors") or []),
                "tables_count": (metadata.get("objects") or {}).get("tables_count", 0),
                "figures_count": (metadata.get("objects") or {}).get("figures_count", 0),
                "warnings_count": len(warnings),
            },
            "warnings": warnings,
            "next_status": "structure_extracted",
        }


def _overlay_author_provided_fields(metadata: dict[str, Any], submission_metadata: dict[str, Any]) -> dict[str, Any]:
    field_map = {
        "abstract": "abstract_ru",
        "keywords": "keywords_ru",
        "supervisor": "supervisor",
        "title": "title_ru",
    }
    merged = dict(metadata)
    for extracted_key, submission_key in field_map.items():
        if merged.get(extracted_key):
            continue
        author_value = submission_metadata.get(submission_key)
        if author_value:
            merged[extracted_key] = author_value
    return merged


class FormatToTemplateStage(BaseWorkflowStage):
    stage_id = "format_to_template"
    title = "Приведение материала к шаблону"
    description = "Создаёт formatted_material.docx и formatting_report.json."
    enabled = True

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        _, format_to_template, load_extracted_metadata, _ = _load_docx_service_functions()
        service = SubmissionService()
        submission_id = submission["submission_id"]
        files = submission.get("files") or {}
        if submission.get("status") == "error":
            return {
                "status": "skipped",
                "message": "Форматирование пропущено после ошибки извлечения DOCX.",
            }

        metadata_value = files.get(FILE_TYPE_EXTRACTED_METADATA)
        source_value = files.get(FILE_TYPE_REVISION_DOCX) or files.get(FILE_TYPE_ORIGINAL_DOCX)
        if not metadata_value:
            return {
                "status": "skipped",
                "message": "Форматирование пропущено: extracted_metadata.json ещё не создан.",
            }

        metadata_path = resolve_stored_file_path(metadata_value)
        source_path = resolve_stored_file_path(source_value) if source_value else None
        metadata = load_extracted_metadata(str(metadata_path))
        if not metadata:
            return {
                "status": "failed",
                "message": "Не удалось прочитать extracted_metadata.json.",
                "next_status": "error",
            }
        metadata = _overlay_author_provided_fields(metadata, submission.get("metadata") or {})
        template_path = Path(settings.CONFERENCE_TEMPLATE_PATH)
        if not template_path.exists():
            return {
                "status": "failed",
                "message": f"Шаблон конференции не найден: {template_path}",
                "next_status": "error",
            }

        output_dir = _submission_output_dir(submission_id)
        formatted_path = output_dir / "formatted_material.docx"
        report_path = output_dir / "formatting_report.json"

        report = format_to_template(
            metadata,
            str(template_path),
            str(formatted_path),
            output_report_path=str(report_path),
            original_docx_path=str(source_path) if source_path else None,
        )
        status = _normalise_status(str(report.get("status", "failed")))
        if not report_path.exists():
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        report_file = service.save_or_update_file_path(
            submission_id,
            FILE_TYPE_FORMATTING_REPORT,
            str(report_path),
        )
        formatted_file: dict[str, Any] | None = None
        if report.get("output_docx") and formatted_path.exists():
            formatted_file = service.save_or_update_file_path(
                submission_id,
                FILE_TYPE_FORMATTED_DOCX,
                str(formatted_path),
            )

        if status == "failed" or not formatted_file:
            return {
                "status": "failed",
                "message": "Не удалось сформировать DOCX по шаблону.",
                "report_file": report_file["path"],
                "report": report,
                "next_status": "error",
            }

        warnings = report.get("warnings", []) or []
        return {
            "status": status,
            "message": (
                "Материал приведён к шаблону с предупреждениями."
                if status == "warning"
                else "Материал успешно приведён к шаблону конференции."
            ),
            "formatted_docx": formatted_file["path"],
            "report_file": report_file["path"],
            "filled_fields": report.get("filled_fields", []),
            "missing_fields": report.get("missing_fields", []),
            "warnings": warnings,
            "next_status": "formatted",
        }


def register_docx_stages() -> None:
    """Register the external DOCX stages exactly once."""
    from submissions.plugin_registry import registry

    registered_ids = {stage.stage_id for stage in registry.list()}
    if ExtractMetadataStage.stage_id not in registered_ids:
        registry.register(ExtractMetadataStage())
    if FormatToTemplateStage.stage_id not in registered_ids:
        registry.register(FormatToTemplateStage())
