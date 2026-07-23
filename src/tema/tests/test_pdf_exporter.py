"""
Тесты модуля docx_processing/pdf_exporter.py (задание 22 ТЗ, п.22.5 «есть тесты»).
"""

import shutil
from pathlib import Path

import pytest

from docx_processing.pdf_exporter import (
    PdfExportErrorCode,
    export_docx_to_pdf,
    is_libreoffice_available,
)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "input_materials"
SAMPLE_DOCX = SAMPLES_DIR / "sample_formatted_material.docx"


@pytest.mark.skipif(not is_libreoffice_available(), reason="LibreOffice не установлен в окружении")
def test_export_success(tmp_path):
    result = export_docx_to_pdf(SAMPLE_DOCX, tmp_path)

    assert result.status == "success"
    assert result.pdf_path is not None
    pdf_path = Path(result.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    assert pdf_path.suffix == ".pdf"


def test_export_source_not_found(tmp_path):
    result = export_docx_to_pdf(tmp_path / "does_not_exist.docx", tmp_path)

    assert result.status == "failed"
    assert result.error_code == PdfExportErrorCode.SOURCE_NOT_FOUND
    assert result.error  # понятное сообщение об ошибке присутствует


def test_export_unsupported_format(tmp_path):
    fake_doc = tmp_path / "material.doc"
    fake_doc.write_bytes(b"not a real doc file")

    result = export_docx_to_pdf(fake_doc, tmp_path)

    assert result.status == "failed"
    assert result.error_code == PdfExportErrorCode.UNSUPPORTED_FORMAT


def test_export_when_libreoffice_missing(tmp_path, monkeypatch):
    import docx_processing.pdf_exporter as pdf_exporter_module

    monkeypatch.setattr(pdf_exporter_module, "_SOFFICE_BIN", None)
    result = pdf_exporter_module.export_docx_to_pdf(SAMPLE_DOCX, tmp_path)

    assert result.status == "failed"
    assert result.error_code == PdfExportErrorCode.SOFFICE_NOT_FOUND


@pytest.mark.skipif(not is_libreoffice_available(), reason="LibreOffice не установлен в окружении")
def test_export_formatted_material_wrapper(tmp_path):
    from docx_processing.pdf_exporter import export_formatted_material

    submission_dir = tmp_path / "SUB-TEST-0001"
    submission_dir.mkdir()
    shutil.copy(SAMPLE_DOCX, submission_dir / "formatted_material.docx")

    result = export_formatted_material(submission_dir)

    assert result.status == "success"
    assert Path(result.pdf_path).name == "formatted_material.pdf"
    assert (submission_dir / "formatted_material.pdf").exists()
