"""
docx_processing/pdf_exporter.py

Модуль конвертации DOCX в PDF.
Реализует пункт 22 технического задания («Задание студенту 3.
PDF-экспорт и формирование файлов результата»), раздел 22.2:

    - принимать formatted_material.docx;
    - конвертировать DOCX в PDF;
    - проверять, что PDF создан;
    - сохранять PDF в папку заявки;
    - возвращать понятную ошибку, если PDF не создан.

Конвертация выполняется через LibreOffice в headless-режиме, так как это
единственный надёжный способ получить PDF, полностью сохраняющий
форматирование Word-документа без сторонних платных сервисов.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --- Константы -------------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_RETRIES = 1  # число ДОПОЛНИТЕЛЬНЫХ попыток после первой неудачной


def _detect_soffice_bin() -> Optional[str]:
    """
    Определяет путь к бинарнику LibreOffice:
      1. Переменная окружения SOFFICE_BIN_PATH — задаётся в .env/окружении,
         а не в коде. Нужна для нестандартных или portable-установок,
         где soffice.exe не попадает в PATH.
      2. Поиск в PATH (shutil.which) — стандартный случай для большинства
         установок LibreOffice.

    Никаких зашитых в код путей к конкретным папкам установки —
    окружение у каждого разработчика/сервера своё, и такие пути только
    создают ложное ощущение переносимости.
    """
    env_path = os.environ.get("SOFFICE_BIN_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    return shutil.which("soffice") or shutil.which("libreoffice")


# Путь к бинарнику LibreOffice определяется один раз при импорте модуля.
_SOFFICE_BIN = _detect_soffice_bin()


# --- Коды ошибок -------------------------------------------------------------
# Единый набор кодов, чтобы редакторский интерфейс и интерфейс автора могли
# показывать понятные сообщения, не разбирая текст ошибки.

class PdfExportErrorCode:
    SOFFICE_NOT_FOUND = "soffice_not_found"
    SOURCE_NOT_FOUND = "source_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    TIMEOUT = "conversion_timeout"
    CONVERSION_FAILED = "conversion_failed"
    EMPTY_OUTPUT = "empty_output"


_ERROR_MESSAGES_RU = {
    PdfExportErrorCode.SOFFICE_NOT_FOUND: "LibreOffice не установлен или недоступен в системе.",
    PdfExportErrorCode.SOURCE_NOT_FOUND: "Исходный DOCX-файл не найден.",
    PdfExportErrorCode.UNSUPPORTED_FORMAT: "Поддерживаются только файлы с расширением .docx.",
    PdfExportErrorCode.TIMEOUT: "Превышено время ожидания конвертации в PDF.",
    PdfExportErrorCode.CONVERSION_FAILED: "Не удалось преобразовать документ в PDF.",
    PdfExportErrorCode.EMPTY_OUTPUT: "PDF-файл был создан, но оказался пустым.",
}


@dataclass
class ExportResult:
    """Результат конвертации одного DOCX-файла в PDF."""

    status: str  # "success" | "failed"
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


def _make_error(code: str, details: str = "", attempts: int = 0, log: str = "") -> ExportResult:
    message = _ERROR_MESSAGES_RU.get(code, "Неизвестная ошибка конвертации.")
    if details:
        message = f"{message} ({details})"
    return ExportResult(status="failed", error=message, error_code=code, attempts=attempts, log=log)


def is_libreoffice_available() -> bool:
    """Проверяет, установлен ли LibreOffice в системе."""
    return _SOFFICE_BIN is not None


def export_docx_to_pdf(
    docx_path: str | Path,
    output_dir: str | Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
) -> ExportResult:
    """
    Конвертирует один DOCX-файл в PDF через LibreOffice headless.

    Параметры:
        docx_path: путь к исходному formatted_material.docx.
        output_dir: папка заявки, куда должен быть сохранён PDF
                    (обычно storage/submissions/<submission_id>/).
        timeout: максимальное время ожидания одной попытки конвертации, сек.
        retries: сколько раз повторить конвертацию при неудаче.

    Возвращает ExportResult. Модуль никогда не поднимает исключение наружу —
    все ошибки заворачиваются в ExportResult(status="failed", ...), чтобы
    сбой конвертации не "ронял" весь конвейер обработки заявки (см. п. 10 ТЗ:
    "не ломать всю систему при ошибке").
    """
    docx_path = Path(docx_path)
    output_dir = Path(output_dir)

    # Сначала проверяем сам запрос (что просят сконвертировать), и только
    # потом — доступность LibreOffice. Иначе при отсутствующем LibreOffice
    # любая ошибка маскировалась бы под "soffice_not_found", даже если
    # реальная причина в неверном пути или расширении файла.
    if not docx_path.exists():
        return _make_error(PdfExportErrorCode.SOURCE_NOT_FOUND, details=str(docx_path))

    if docx_path.suffix.lower() != ".docx":
        return _make_error(PdfExportErrorCode.UNSUPPORTED_FORMAT, details=docx_path.suffix)

    if _SOFFICE_BIN is None:
        return _make_error(PdfExportErrorCode.SOFFICE_NOT_FOUND)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _make_error(PdfExportErrorCode.CONVERSION_FAILED, details=f"нет доступа к папке заявки: {exc}")

    expected_pdf = output_dir / (docx_path.stem + ".pdf")

    last_log = ""
    attempts_made = 0
    total_attempts = 1 + max(retries, 0)

    for attempt in range(1, total_attempts + 1):
        attempts_made = attempt
        try:
            proc = subprocess.run(
                [
                    _SOFFICE_BIN,
                    "--headless",
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
            )
            last_log = (proc.stdout or "") + (proc.stderr or "")

            if expected_pdf.exists():
                if expected_pdf.stat().st_size > 0:
                    return ExportResult(
                        status="success",
                        pdf_path=str(expected_pdf),
                        attempts=attempt,
                        log=last_log,
                    )
                # Файл создан, но пустой — считаем попытку неудачной и, если
                # остались попытки, пробуем ещё раз.
                expected_pdf.unlink(missing_ok=True)
                last_log += "\n[warn] Итоговый PDF-файл был пустым, удалён."

        except subprocess.TimeoutExpired:
            last_log = f"Таймаут конвертации после {timeout} с."
            return _make_error(PdfExportErrorCode.TIMEOUT, attempts=attempt, log=last_log)
        except Exception as exc:  # защищаемся от любых непредвиденных сбоев
            last_log = f"{type(exc).__name__}: {exc}"

    # Все попытки исчерпаны
    if expected_pdf.exists() and expected_pdf.stat().st_size == 0:
        return _make_error(PdfExportErrorCode.EMPTY_OUTPUT, attempts=attempts_made, log=last_log)

    return _make_error(
        PdfExportErrorCode.CONVERSION_FAILED,
        details=last_log.strip().splitlines()[-1] if last_log.strip() else "",
        attempts=attempts_made,
        log=last_log,
    )


def export_formatted_material(submission_dir: str | Path, **kwargs) -> ExportResult:
    """
    Удобная обёртка над export_docx_to_pdf для стандартной структуры заявки:
    ожидает файл formatted_material.docx внутри submission_dir и сохраняет
    formatted_material.pdf туда же.
    """
    submission_dir = Path(submission_dir)
    return export_docx_to_pdf(
        docx_path=submission_dir / "formatted_material.docx",
        output_dir=submission_dir,
        **kwargs,
    )
