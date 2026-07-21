"""Build an author-facing ZIP without internal JSON artifacts."""

from __future__ import annotations

import zipfile
from pathlib import Path

from .file_registry import collect_result_files


AUTHOR_PACKAGE_FILE_TYPES = (
    "formatted_docx",
    "formatted_pdf",
    "author_report",
)


def build_result_zip(submission_dir: str | Path, output_zip_path: str | Path) -> dict:
    submission_dir = Path(submission_dir).resolve()
    output_zip_path = Path(output_zip_path).resolve()
    manifest = collect_result_files(submission_dir)
    available = [
        manifest["files"][file_type]
        for file_type in AUTHOR_PACKAGE_FILE_TYPES
        if manifest["files"][file_type]["available"]
    ]
    if not available:
        return {
            "status": "failed",
            "error": "В папке заявки не найдено ни одного файла результата — архивировать нечего.",
            "zip_path": None,
            "included_files": [],
            "missing_files": manifest["missing_files"],
        }

    try:
        output_zip_path.parent.mkdir(parents=True, exist_ok=True)
        output_zip_path.unlink(missing_ok=True)
        included: list[str] = []
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for info in available:
                path = submission_dir / info["path"]
                archive.write(path, arcname=info["filename"])
                included.append(info["filename"])
    except (OSError, zipfile.BadZipFile) as exc:
        output_zip_path.unlink(missing_ok=True)
        return {
            "status": "failed",
            "error": f"Ошибка при создании ZIP-архива: {exc}",
            "zip_path": None,
            "included_files": [],
            "missing_files": manifest["missing_files"],
        }

    status = "success" if not manifest["missing_files"] else "partial"
    return {
        "status": status,
        "error": None,
        "zip_path": str(output_zip_path),
        "included_files": included,
        "missing_files": manifest["missing_files"],
        "missing_required_files": manifest["missing_required_files"],
        "missing_optional_files": manifest["missing_optional_files"],
    }
