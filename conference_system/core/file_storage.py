from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from conference_system.app.config import settings

SAFE_FILE_TYPES = {
    "original_docx": "original.docx",
    "formatted_docx": "formatted_material.docx",
    "formatted_pdf": "formatted_material.pdf",
    "check_report": "check_report.json",
    "extracted_metadata": "extracted_metadata.json",
    "formatting_report": "formatting_report.json",
    "author_report": "author_report.pdf",
    "revision_docx": "revision.docx",
}


def submission_dir(submission_id: str) -> Path:
    path = settings.storage_dir / "submissions" / submission_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_path(submission_id: str, file_type: str, original_name: str | None = None) -> Path:
    if file_type == "revision_docx":
        rev_dir = submission_dir(submission_id) / "revisions"
        rev_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return rev_dir / f"revision_{stamp}.docx"
    filename = SAFE_FILE_TYPES.get(file_type)
    if not filename:
        suffix = Path(original_name or "file.bin").suffix or ".bin"
        filename = f"{file_type}{suffix}"
    return submission_dir(submission_id) / filename


def save_upload(submission_id: str, file_type: str, file_obj: BinaryIO, original_name: str = "") -> str:
    path = get_file_path(submission_id, file_type, original_name)
    with path.open("wb") as out:
        shutil.copyfileobj(file_obj, out)
    return str(path)


def save_json(submission_id: str, file_type: str, payload: dict[str, Any]) -> str:
    path = get_file_path(submission_id, file_type, f"{file_type}.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def ensure_demo_result_files(submission_id: str) -> None:
    """Create small placeholder result files so the author UI can demonstrate downloads."""
    folder = submission_dir(submission_id)
    formatted_docx = folder / "formatted_material.docx"
    formatted_pdf = folder / "formatted_material.pdf"
    check_report = folder / "check_report.json"
    if not formatted_docx.exists():
        formatted_docx.write_bytes(b"Placeholder formatted DOCX. Replace by DOCX module.")
    if not formatted_pdf.exists():
        formatted_pdf.write_bytes(b"%PDF-1.4\n% Placeholder PDF. Replace by PDF exporter module.\n")
    if not check_report.exists():
        check_report.write_text(
            json.dumps(
                {
                    "overall_status": "demo",
                    "author_message": "Демонстрационный отчёт. Реальные проверки добавляет модуль проверок.",
                    "checks": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
