from __future__ import annotations

from pathlib import Path

from ..pdf_export.pdf_exporter import export_formatted_material
from .file_registry import collect_result_files, save_manifest
from .package_builder import build_result_zip

MANIFEST_FILENAME = "result_manifest.json"
ZIP_FILENAME = "result_package.zip"


def finalize_submission_files(submission_dir: str | Path) -> dict:
    submission_dir = Path(submission_dir).resolve()
    report: dict = {
        "submission_dir": str(submission_dir),
        "status": "failed",
        "message": "",
        "warnings": [],
        "errors": [],
        "steps": [],
    }

    formatted_docx = submission_dir / "formatted_material.docx"
    if not formatted_docx.is_file():
        message = (
            "Не найден formatted_material.docx. Сначала должен завершиться "
            "этап приведения материала к шаблону конференции."
        )
        report["message"] = message
        report["errors"].append(message)
        return report

    pdf_result = export_formatted_material(submission_dir)
    report["steps"].append({"step": "pdf_export", **pdf_result.to_dict()})
    if pdf_result.status != "success":
        report["message"] = pdf_result.error or "PDF не был создан."
        report["errors"].append(report["message"])
        return report

    manifest = collect_result_files(submission_dir)
    manifest_path = save_manifest(manifest, submission_dir / MANIFEST_FILENAME)
    report["steps"].append(
        {
            "step": "collect_result_files",
            "status": "success",
            "manifest_path": manifest_path,
            "missing_files": manifest["missing_files"],
        }
    )

    zip_result = build_result_zip(submission_dir, submission_dir / ZIP_FILENAME)
    report["steps"].append({"step": "build_result_zip", **zip_result})
    report["manifest"] = manifest
    report["manifest_path"] = manifest_path
    report["zip"] = zip_result
    report["pdf_path"] = pdf_result.pdf_path

    if zip_result["status"] == "failed":
        report["message"] = zip_result.get("error") or "ZIP-пакет не был создан."
        report["errors"].append(report["message"])
        return report

    if manifest["missing_required_files"]:
        report["status"] = "warning"
        report["message"] = "PDF создан, но обязательная часть пакета неполна."
        report["warnings"].append(
            "Отсутствуют обязательные файлы: " + ", ".join(manifest["missing_required_files"])
        )
    elif manifest["missing_optional_files"]:
        report["status"] = "warning"
        report["message"] = "PDF и ZIP созданы; отчёты следующих этапов пока не добавлены."
        report["warnings"].append(
            "Пока отсутствуют файлы следующих модулей: " + ", ".join(manifest["missing_optional_files"])
        )
    else:
        report["status"] = "success"
        report["message"] = "PDF и полный ZIP-пакет успешно сформированы."
    return report
