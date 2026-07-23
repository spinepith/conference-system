from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_RETRIES = 1


class PdfExportErrorCode:
    SOFFICE_NOT_FOUND = "soffice_not_found"
    SOURCE_NOT_FOUND = "source_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    TIMEOUT = "conversion_timeout"
    CONVERSION_FAILED = "conversion_failed"
    EMPTY_OUTPUT = "empty_output"
    INVALID_OUTPUT = "invalid_output"


_ERROR_MESSAGES_RU = {
    PdfExportErrorCode.SOFFICE_NOT_FOUND: "LibreOffice не установлен или недоступен в системе.",
    PdfExportErrorCode.SOURCE_NOT_FOUND: "Исходный DOCX-файл не найден.",
    PdfExportErrorCode.UNSUPPORTED_FORMAT: "Поддерживаются только файлы с расширением .docx.",
    PdfExportErrorCode.TIMEOUT: "Превышено время ожидания конвертации в PDF.",
    PdfExportErrorCode.CONVERSION_FAILED: "Не удалось преобразовать документ в PDF.",
    PdfExportErrorCode.EMPTY_OUTPUT: "PDF-файл был создан, но оказался пустым.",
    PdfExportErrorCode.INVALID_OUTPUT: "Созданный файл не является корректным PDF.",
}


@dataclass
class ExportResult:
    status: str
    pdf_path: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    attempts: int = 0
    log: str = field(default="", repr=False)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "pdf_path": self.pdf_path,
            "error": self.error,
            "error_code": self.error_code,
            "attempts": self.attempts,
        }


def _detect_soffice_bin() -> Optional[str]:
    env_path = os.environ.get("SOFFICE_BIN_PATH", "").strip().strip('"')
    if env_path and Path(env_path).exists():
        return str(Path(env_path))
    return shutil.which("soffice") or shutil.which("libreoffice")


def is_libreoffice_available() -> bool:
    return _detect_soffice_bin() is not None


def _make_error(code: str, details: str = "", attempts: int = 0, log: str = "") -> ExportResult:
    message = _ERROR_MESSAGES_RU.get(code, "Неизвестная ошибка конвертации.")
    if details:
        message = f"{message} ({details})"
    return ExportResult(
        status="failed",
        error=message,
        error_code=code,
        attempts=attempts,
        log=log,
    )


def _is_valid_pdf(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size < 5:
        return False
    try:
        with path.open("rb") as fh:
            return fh.read(5) == b"%PDF-"
    except OSError:
        return False


def export_docx_to_pdf(
    docx_path: str | Path,
    output_dir: str | Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
) -> ExportResult:
    docx_path = Path(docx_path).resolve()
    output_dir = Path(output_dir).resolve()

    if not docx_path.exists():
        return _make_error(PdfExportErrorCode.SOURCE_NOT_FOUND, str(docx_path))
    if docx_path.suffix.lower() != ".docx":
        return _make_error(PdfExportErrorCode.UNSUPPORTED_FORMAT, docx_path.suffix)

    soffice_bin = _detect_soffice_bin()
    if not soffice_bin:
        return _make_error(
            PdfExportErrorCode.SOFFICE_NOT_FOUND,
            "установите LibreOffice и добавьте soffice в PATH либо задайте SOFFICE_BIN_PATH",
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _make_error(PdfExportErrorCode.CONVERSION_FAILED, f"нет доступа к папке: {exc}")

    expected_pdf = output_dir / f"{docx_path.stem}.pdf"
    expected_pdf.unlink(missing_ok=True)  # old PDF must never mask a failed new conversion

    last_log = ""
    attempts_made = 0
    for attempt in range(1, 2 + max(retries, 0)):
        attempts_made = attempt
        try:
            process = subprocess.run(
                [
                    soffice_bin,
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nolockcheck",
                    "--norestore",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(docx_path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            last_log = ((process.stdout or "") + "\n" + (process.stderr or "")).strip()
            if process.returncode == 0 and _is_valid_pdf(expected_pdf):
                return ExportResult(
                    status="success",
                    pdf_path=str(expected_pdf),
                    attempts=attempt,
                    log=last_log,
                )
            expected_pdf.unlink(missing_ok=True)
        except subprocess.TimeoutExpired:
            expected_pdf.unlink(missing_ok=True)
            return _make_error(PdfExportErrorCode.TIMEOUT, attempts=attempt, log=last_log)
        except OSError as exc:
            last_log = f"{type(exc).__name__}: {exc}"

    if expected_pdf.exists() and expected_pdf.stat().st_size == 0:
        return _make_error(PdfExportErrorCode.EMPTY_OUTPUT, attempts=attempts_made, log=last_log)
    if expected_pdf.exists() and not _is_valid_pdf(expected_pdf):
        expected_pdf.unlink(missing_ok=True)
        return _make_error(PdfExportErrorCode.INVALID_OUTPUT, attempts=attempts_made, log=last_log)
    details = last_log.splitlines()[-1] if last_log else "LibreOffice не создал итоговый PDF"
    return _make_error(PdfExportErrorCode.CONVERSION_FAILED, details, attempts_made, last_log)


def export_formatted_material(submission_dir: str | Path, **kwargs) -> ExportResult:
    submission_dir = Path(submission_dir)
    return export_docx_to_pdf(
        submission_dir / "formatted_material.docx",
        submission_dir,
        **kwargs,
    )
