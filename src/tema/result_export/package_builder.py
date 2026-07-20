"""Build a ZIP package from available result files."""

from __future__ import annotations

import zipfile
from pathlib import Path

from .file_registry import collect_result_files


def build_result_zip(submission_dir: str | Path, output_zip_path: str | Path) -> dict:
    submission_dir = Path(submission_dir).resolve()
    output_zip_path = Path(output_zip_path).resolve()
    manifest = collect_result_files(submission_dir)
    available = [info for info in manifest["files"].values() if info["available"]]
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
            manifest_path = submission_dir / "result_manifest.json"
            if manifest_path.is_file():
                archive.write(manifest_path, arcname=manifest_path.name)
                included.append(manifest_path.name)
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
