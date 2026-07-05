"""
result_export/package_builder.py

Реализует пункт 22.2 ТЗ: «формировать ZIP-пакет результата».

Собирает все фактически существующие файлы заявки (см. file_registry.py)
в единый ZIP-архив, который редактор или автор может скачать одним файлом.
Если часть файлов отсутствует, пакет всё равно собирается из того, что
есть (status="partial"), а не падает с ошибкой — это соответствует общему
принципу ТЗ «не ломать всю систему при ошибке» (п. 10).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from .file_registry import collect_result_files


def build_result_zip(
    submission_dir: str | Path,
    output_zip_path: str | Path,
) -> dict:
    """
    Строит ZIP-архив из доступных файлов заявки.

    Возвращает словарь:
        {
          "status": "success" | "partial" | "failed",
          "error": str | None,
          "zip_path": str | None,
          "included_files": [...],
          "missing_files": [...],
        }

    status:
        "success" — заархивированы все ожидаемые файлы;
        "partial" — заархивирована часть файлов, каких-то не хватает;
        "failed"  — не удалось создать архив вообще
                    (нет ни одного файла или ошибка записи на диск).
    """
    submission_dir = Path(submission_dir)
    output_zip_path = Path(output_zip_path)
    manifest = collect_result_files(submission_dir)

    available_files = [info for info in manifest["files"].values() if info["available"]]
    if not available_files:
        return {
            "status": "failed",
            "error": "В папке заявки не найдено ни одного файла результата — архивировать нечего.",
            "zip_path": None,
            "included_files": [],
            "missing_files": manifest["missing_files"],
        }

    try:
        output_zip_path.parent.mkdir(parents=True, exist_ok=True)
        included_files = []
        with zipfile.ZipFile(output_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for info in available_files:
                zf.write(info["path"], arcname=info["filename"])
                included_files.append(info["filename"])
    except OSError as exc:
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
        "included_files": included_files,
        "missing_files": manifest["missing_files"],
    }
