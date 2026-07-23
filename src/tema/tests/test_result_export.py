"""
Тесты модулей result_export/* и интеграционного сервиса
(задание 22 ТЗ, п.22.5 «есть тесты»).
"""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from result_export.file_registry import collect_result_files, save_manifest
from result_export.package_builder import build_result_zip
from docx_processing.pdf_exporter import is_libreoffice_available

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "input_materials"
SAMPLE_DOCX = SAMPLES_DIR / "sample_formatted_material.docx"


def _make_full_submission(submission_dir: Path) -> None:
    """Создаёт папку заявки со всеми ожидаемыми файлами результата, кроме PDF."""
    submission_dir.mkdir(parents=True)
    shutil.copy(SAMPLE_DOCX, submission_dir / "original.docx")
    shutil.copy(SAMPLE_DOCX, submission_dir / "formatted_material.docx")
    (submission_dir / "extracted_metadata.json").write_text(
        json.dumps({"title": "Тестовый материал"}, ensure_ascii=False), encoding="utf-8"
    )
    (submission_dir / "formatting_report.json").write_text(
        json.dumps({"status": "success"}, ensure_ascii=False), encoding="utf-8"
    )
    (submission_dir / "check_report.json").write_text(
        json.dumps({"overall_status": "passed"}, ensure_ascii=False), encoding="utf-8"
    )


# --- file_registry -----------------------------------------------------------

def test_collect_result_files_all_missing(tmp_path):
    submission_dir = tmp_path / "SUB-EMPTY"
    submission_dir.mkdir()

    manifest = collect_result_files(submission_dir)

    assert manifest["is_complete_for_author"] is False
    assert set(manifest["missing_files"]) == {
        "original_docx",
        "formatted_docx",
        "formatted_pdf",
        "extracted_metadata",
        "formatting_report",
        "check_report",
        "author_report",
    }
    assert all(not info["available"] for info in manifest["files"].values())


def test_collect_result_files_partial(tmp_path):
    submission_dir = tmp_path / "SUB-PARTIAL"
    _make_full_submission(submission_dir)
    # PDF и author_report сознательно не создаём.

    manifest = collect_result_files(submission_dir)

    assert manifest["files"]["formatted_docx"]["available"] is True
    assert manifest["files"]["formatted_pdf"]["available"] is False
    assert "formatted_pdf" in manifest["missing_files"]
    assert manifest["is_complete_for_author"] is False  # PDF обязателен


def test_collect_result_files_author_report_either_extension(tmp_path):
    submission_dir = tmp_path / "SUB-AR"
    _make_full_submission(submission_dir)
    (submission_dir / "formatted_material.pdf").write_bytes(b"%PDF-1.4 fake")
    (submission_dir / "author_report.docx").write_bytes(b"fake docx content")

    manifest = collect_result_files(submission_dir)

    assert manifest["files"]["author_report"]["available"] is True
    assert manifest["files"]["author_report"]["filename"] == "author_report.docx"
    assert manifest["is_complete_for_author"] is True


def test_save_manifest(tmp_path):
    submission_dir = tmp_path / "SUB-SAVE"
    submission_dir.mkdir()
    manifest = collect_result_files(submission_dir)

    output_path = tmp_path / "result_manifest.json"
    save_manifest(manifest, output_path)

    assert output_path.exists()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["submission_dir"] == manifest["submission_dir"]


# --- package_builder -----------------------------------------------------------

def test_build_result_zip_no_files(tmp_path):
    submission_dir = tmp_path / "SUB-NOFILES"
    submission_dir.mkdir()

    result = build_result_zip(submission_dir, tmp_path / "out.zip")

    assert result["status"] == "failed"
    assert result["zip_path"] is None
    assert result["error"]


def test_build_result_zip_partial(tmp_path):
    submission_dir = tmp_path / "SUB-ZIP-PARTIAL"
    _make_full_submission(submission_dir)

    output_zip = tmp_path / "result_package.zip"
    result = build_result_zip(submission_dir, output_zip)

    assert result["status"] == "partial"
    assert output_zip.exists()
    assert "formatted_pdf" in result["missing_files"]

    with zipfile.ZipFile(output_zip) as zf:
        names = zf.namelist()
    assert "formatted_material.docx" in names
    assert "check_report.json" in names


def test_build_result_zip_complete(tmp_path):
    submission_dir = tmp_path / "SUB-ZIP-FULL"
    _make_full_submission(submission_dir)
    (submission_dir / "formatted_material.pdf").write_bytes(b"%PDF-1.4 fake")
    (submission_dir / "author_report.pdf").write_bytes(b"%PDF-1.4 fake")

    output_zip = tmp_path / "result_package.zip"
    result = build_result_zip(submission_dir, output_zip)

    assert result["status"] == "success"
    assert result["missing_files"] == []
    with zipfile.ZipFile(output_zip) as zf:
        assert len(zf.namelist()) == 7


# --- service (интеграционный тест) --------------------------------------------

@pytest.mark.skipif(not is_libreoffice_available(), reason="LibreOffice не установлен в окружении")
def test_finalize_submission_files_end_to_end(tmp_path):
    from result_export.service import finalize_submission_files

    submission_dir = tmp_path / "SUB-2026-Q1-TEST"
    _make_full_submission(submission_dir)

    report = finalize_submission_files(submission_dir)

    assert report["status"] in ("success", "partial")
    assert (submission_dir / "formatted_material.pdf").exists()
    assert (submission_dir / "result_manifest.json").exists()
    assert (submission_dir / "result_package.zip").exists()
    # author_report не создавался этим модулем -> ожидаем partial с одной недостачей
    assert report["manifest"]["missing_files"] == ["author_report"]


def test_finalize_submission_files_missing_formatted_docx(tmp_path):
    from result_export.service import finalize_submission_files

    submission_dir = tmp_path / "SUB-NO-FORMATTED"
    submission_dir.mkdir()

    report = finalize_submission_files(submission_dir)

    assert report["status"] == "failed"
    assert "formatted_material.docx" in report["error"]
