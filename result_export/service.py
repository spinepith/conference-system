"""
result_export/service.py

Точка входа модуля студента 3: связывает воедино шаги пункта 22 ТЗ
("PDF-экспорт и формирование файлов результата") в единый вызов,
который использует ядро системы (студент 1) как этап workflow.

Ожидаемый вход: submission_dir — папка заявки, в которой модуль
приведения к шаблону (студент 2, п.21) уже сохранил formatted_material.docx.

Шаги:
    1. Конвертировать formatted_material.docx -> formatted_material.pdf.
    2. Собрать реестр всех файлов результата и сохранить его в JSON.
    3. Собрать ZIP-пакет результата.

Функция не бросает исключения — при любой ошибке возвращает
структурированный результат со status="failed" и понятным сообщением,
пригодным для показа автору/редактору (см. п. 10, 22.5 ТЗ).
"""

from __future__ import annotations

from pathlib import Path

from docx_processing.pdf_exporter import export_formatted_material
from result_export.file_registry import collect_result_files, save_manifest
from result_export.package_builder import build_result_zip

MANIFEST_FILENAME = "result_manifest.json"
ZIP_FILENAME = "result_package.zip"


def finalize_submission_files(submission_dir: str | Path) -> dict:
    """
    Выполняет полный цикл "PDF-экспорт + сборка файлов результата" для
    одной заявки. Предназначена для вызова из workflow-этапа
    (например, "export_pdf_and_package") в ядре системы студента 1.
    """
    submission_dir = Path(submission_dir)
    report: dict = {"submission_dir": str(submission_dir), "steps": []}

    formatted_docx = submission_dir / "formatted_material.docx"
    if not formatted_docx.exists():
        report["status"] = "failed"
        report["error"] = (
            "Не найден formatted_material.docx. Сначала должен отработать "
            "модуль приведения материала к шаблону конференции."
        )
        return report

    # Шаг 1. PDF-экспорт.
    pdf_result = export_formatted_material(submission_dir)
    report["steps"].append(
        {
            "step": "pdf_export",
            "status": pdf_result.status,
            "error": pdf_result.error,
            "pdf_path": pdf_result.pdf_path,
        }
    )
    if pdf_result.status != "success":
        report["status"] = "failed"
        report["error"] = pdf_result.error
        return report

    # Шаг 2. Реестр файлов результата.
    manifest = collect_result_files(submission_dir)
    save_manifest(manifest, submission_dir / MANIFEST_FILENAME)
    report["steps"].append(
        {
            "step": "collect_result_files",
            "status": "success",
            "missing_files": manifest["missing_files"],
        }
    )

    # Шаг 3. ZIP-пакет.
    zip_result = build_result_zip(submission_dir, submission_dir / ZIP_FILENAME)
    report["steps"].append(
        {
            "step": "build_result_zip",
            "status": zip_result["status"],
            "error": zip_result["error"],
            "zip_path": zip_result["zip_path"],
        }
    )

    report["manifest"] = manifest
    report["zip"] = zip_result
    report["status"] = "success" if zip_result["status"] in ("success", "partial") else "failed"
    if report["status"] == "failed" and not report.get("error"):
        report["error"] = zip_result["error"]

    return report
