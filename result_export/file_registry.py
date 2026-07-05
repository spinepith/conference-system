"""
result_export/file_registry.py

Реализует пункт 22.3 ТЗ («Файлы результата»): формирует единый реестр
(manifest) файлов заявки, показывая, какие из ожидаемых файлов результата
фактически существуют в папке заявки, а каких не хватает.

Ожидаемый набор файлов заявки (storage/submissions/<submission_id>/):
    original.docx
    formatted_material.docx
    formatted_material.pdf
    extracted_metadata.json
    formatting_report.json
    check_report.json
    author_report.pdf  (или author_report.docx)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Соответствие "логическое имя файла" -> "имя файла на диске".
# author_report обрабатывается отдельно, т.к. допустимы два расширения.
RESULT_FILE_SPEC: dict[str, Optional[str]] = {
    "original_docx": "original.docx",
    "formatted_docx": "formatted_material.docx",
    "formatted_pdf": "formatted_material.pdf",
    "extracted_metadata": "extracted_metadata.json",
    "formatting_report": "formatting_report.json",
    "check_report": "check_report.json",
    "author_report": None,
}

# Файлы, без которых пакет для автора считается неполным (п. 22 ТЗ).
REQUIRED_FOR_AUTHOR = ("formatted_docx", "formatted_pdf", "check_report")


def _resolve_author_report(submission_dir: Path) -> Optional[Path]:
    for ext in ("pdf", "docx"):
        candidate = submission_dir / f"author_report.{ext}"
        if candidate.exists():
            return candidate
    return None


def collect_result_files(submission_dir: str | Path) -> dict:
    """
    Сканирует папку заявки и строит реестр файлов результата.

    Возвращает словарь вида:
        {
          "submission_dir": "...",
          "files": {
            "formatted_pdf": {
                "path": "...", "filename": "formatted_material.pdf",
                "size_bytes": 12345, "available": True
            },
            ...
          },
          "missing_files": ["author_report"],
          "is_complete_for_author": False
        }
    """
    submission_dir = Path(submission_dir)
    files: dict[str, dict] = {}
    missing: list[str] = []

    for key, filename in RESULT_FILE_SPEC.items():
        if key == "author_report":
            path = _resolve_author_report(submission_dir)
            display_name = path.name if path else "author_report.pdf|.docx"
        else:
            candidate = submission_dir / filename
            path = candidate if candidate.exists() else None
            display_name = filename

        if path is not None:
            files[key] = {
                "path": str(path),
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "available": True,
            }
        else:
            files[key] = {
                "path": None,
                "filename": display_name,
                "size_bytes": 0,
                "available": False,
            }
            missing.append(key)

    return {
        "submission_dir": str(submission_dir),
        "files": files,
        "missing_files": missing,
        "is_complete_for_author": all(files[k]["available"] for k in REQUIRED_FOR_AUTHOR),
    }


def save_manifest(manifest: dict, output_path: str | Path) -> None:
    """Сохраняет реестр файлов в JSON (result_manifest.json)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
