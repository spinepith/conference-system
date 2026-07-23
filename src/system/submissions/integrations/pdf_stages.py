from __future__ import annotations

from pathlib import Path
from typing import Any

from tema.result_export.service import finalize_submission_files

from ..base_stage import BaseWorkflowStage
from ..plugin_registry import registry
from ..services import SubmissionService, resolve_stored_file_path


class ExportPdfAndPackageStage(BaseWorkflowStage):
    stage_id = "export_pdf_and_package"
    title = "PDF-экспорт и пакет файлов"
    description = "Создаёт formatted_material.pdf, result_manifest.json и result_package.zip."

    def run(self, submission: dict[str, Any]) -> dict[str, Any]:
        submission_id = submission["submission_id"]
        formatted_reference = (submission.get("files") or {}).get("formatted_docx")
        if not formatted_reference:
            if submission.get("status") == "error":
                return {
                    "status": "skipped",
                    "message": "PDF-экспорт пропущен: предыдущий этап завершился ошибкой.",
                }
            return {
                "status": "failed",
                "message": "Не найден formatted_material.docx для PDF-экспорта.",
            }

        formatted_path = resolve_stored_file_path(formatted_reference)
        submission_dir = formatted_path.parent
        report = finalize_submission_files(submission_dir)
        service = SubmissionService()

        file_mapping = {
            "formatted_pdf": report.get("pdf_path"),
            "result_manifest": report.get("manifest_path"),
            "result_package": (report.get("zip") or {}).get("zip_path"),
        }
        saved_files: dict[str, str] = {}
        for file_type, path in file_mapping.items():
            if path and Path(path).is_file():
                row = service.save_or_update_file_path(submission_id, file_type, path)
                saved_files[file_type] = row["path"]

        service.add_event(
            submission_id,
            "pdf_package_finished",
            {
                "status": report.get("status"),
                "message": report.get("message"),
                "files": saved_files,
                "warnings": report.get("warnings", []),
                "errors": report.get("errors", []),
            },
        )
        return {
            "status": report.get("status", "failed"),
            "message": report.get("message", "PDF-экспорт завершён."),
            "files": saved_files,
            "warnings": report.get("warnings", []),
            "errors": report.get("errors", []),
            "manifest": report.get("manifest", {}),
            "zip": report.get("zip", {}),
        }


def register_pdf_stages() -> None:
    if "export_pdf_and_package" not in {stage.stage_id for stage in registry.list()}:
        registry.register(ExportPdfAndPackageStage())
