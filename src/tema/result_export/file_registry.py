"""Result file registry for one submission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

RESULT_FILE_SPEC: dict[str, Optional[str]] = {
    "original_docx": "original.docx",
    "formatted_docx": "formatted_material.docx",
    "formatted_pdf": "formatted_material.pdf",
    "extracted_metadata": "extracted_metadata.json",
    "formatting_report": "formatting_report.json",
    "check_report": "check_report.json",
    "author_report": None,
}

# check_report and author_report are produced by later modules and are optional
# at the moment when the PDF stage follows student 2 in the workflow.
REQUIRED_AFTER_FORMATTING = (
    "original_docx",
    "formatted_docx",
    "formatted_pdf",
    "extracted_metadata",
    "formatting_report",
)


def _resolve_author_report(submission_dir: Path) -> Optional[Path]:
    for ext in ("pdf", "docx"):
        candidate = submission_dir / f"author_report.{ext}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def collect_result_files(submission_dir: str | Path) -> dict:
    submission_dir = Path(submission_dir).resolve()
    files: dict[str, dict] = {}
    missing: list[str] = []

    for key, filename in RESULT_FILE_SPEC.items():
        if key == "author_report":
            path = _resolve_author_report(submission_dir)
            display_name = path.name if path else "author_report.pdf|.docx"
        else:
            candidate = submission_dir / str(filename)
            path = candidate if candidate.is_file() and candidate.stat().st_size > 0 else None
            display_name = str(filename)

        files[key] = {
            "path": path.name if path else None,
            "filename": path.name if path else display_name,
            "size_bytes": path.stat().st_size if path else 0,
            "available": bool(path),
        }
        if not path:
            missing.append(key)

    missing_required = [key for key in REQUIRED_AFTER_FORMATTING if not files[key]["available"]]
    missing_optional = [key for key in missing if key not in REQUIRED_AFTER_FORMATTING]
    return {
        "submission_dir": str(submission_dir),
        "files": files,
        "missing_files": missing,
        "missing_required_files": missing_required,
        "missing_optional_files": missing_optional,
        "is_complete_after_formatting": not missing_required,
        "is_complete_for_author": not missing,
    }


def save_manifest(manifest: dict, output_path: str | Path) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)
