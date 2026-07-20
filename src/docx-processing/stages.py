"""
docx_processing.stages — обёртки модуля docx_processing в виде
BaseWorkflowStage (core/base_stage.py), зарегистрированные в
core/plugin_registry.py и вызываемые из core/workflow.py.

Переписано после получения core/models.py, core/plugin_registry.py,
core/workflow.py — все 4 допущения из предыдущей версии закрыты:

1. submission, приходящий в run(submission), — это ЖИВОЙ SQLAlchemy ORM
   объект models.Submission (WorkflowEngine получает его один раз через
   SubmissionService.get_submission() и передаёт один и тот же объект
   всем стадиям подряд в одной сессии/транзакции). Стадия не возвращает
   submission обратно — она мутирует переданный объект напрямую, и
   WorkflowEngine сам делает db.commit() после каждой стадии.

2. Файлы (original_docx, extracted_metadata, formatted_docx,
   formatting_report) — НЕ словарь submission["files"], а отдельная
   таблица SubmissionFile (submission.files: list[SubmissionFile]) с
   уникальным (submission_id, file_type). Ниже — хелперы
   _get_file_path()/_set_file_path(), которые ищут/обновляют нужную
   строку по file_type вместо словаря.

3. submission.metadata_json — это JSON-колонка (атрибут metadata_json,
   имя колонки в БД — "metadata"; имя "metadata" как атрибут занято
   служебным Base.metadata SQLAlchemy, поэтому в models.py оно и
   переименовано). Изменять нужно ПРИСВОЕНИЕМ НОВОГО словаря
   (submission.metadata_json = {...}), а не мутацией текущего — иначе
   SQLAlchemy может не отследить изменение JSON-колонки.

4. authors — НЕ часть metadata_json, а отдельная таблица models.Author
   (submission.authors: list[Author], full_name/email/organization/role).
   Ниже старые Author-записи стадия удаляет и создаёт заново из
   извлечённых ФИО (Author — cascade="all, delete-orphan", поэтому
   submission.authors.clear() корректно поставит старые записи на
   удаление при коммите).

5. run() должен возвращать dict вида {"status", "message", ...}: именно
   так его использует WorkflowEngine.run_submission() — оборачивает в
   WorkflowStageResult (status, message, result_json=весь payload) и
   САМ пишет событие в журнал (core/event_log.add_event) и коммитит.
   Стадии не должны сами открывать сессию, коммитить или логировать
   события — это уже делает WorkflowEngine.

ОСТАЮЩИЕСЯ ОТКРЫТЫЕ ВОПРОСЫ (не закрываются одним только models.py)
-----------------------------------------------------------------
A. Путь к DOCX-шаблону конференции нигде в Conference/Issue не хранится
   (в models.py у Issue нет поля вроде template_path). Пока это
   параметр конструктора FormatToTemplateStage с дефолтом. Если
   шаблон должен настраиваться администратором на выпуск (ТЗ п.5.3,
   "загружать шаблон конференции") — понадобится либо новая колонка
   у Issue, либо отдельная таблица ConferenceTemplate, либо конфиг
   уровня приложения (config.py). Как только решите — здесь достаточно
   поменять DEFAULT_TEMPLATE_PATH / способ его получения в run().
B. Точные строковые значения file_type ("original_docx",
   "extracted_metadata", "formatted_docx", "formatting_report", ...)
   нигде не зафиксированы как константы — их использует и этот модуль,
   и, видимо, author_ui (выгрузка original_docx), issue_builder/PDF-модуль
   (formatted_pdf), checks (check_report). Стоит вынести в общий
   core/file_types.py, чтобы никто не разъехался с опечаткой в строке.
   Пока используются "плоские" строки как показано ниже.
C. submission.status этой стадией НЕ меняется — не видно, кто именно
   переводит статус согласно ТЗ п.6 (formatted, auto_checking, ...):
   либо WorkflowEngine делает это после агрегации результатов всех
   стадий, либо это отдельный вызов SubmissionService.
   update_submission_status(...) поверх результатов run_submission().
   Пока оставляю это зоной ответственности студента 1.
D. models.Author не имеет колонки для англоязычного ФИО — извлечённые
   authors_en (список строк) кладутся в submission.metadata_json как
   плоский список, а не привязываются к конкретному автору. Если нужна
   связка "у автора N есть английское имя" — потребуется добавить
   колонку full_name_en в Author.
"""
from __future__ import annotations

import os
from typing import Any

from conference_system.core.base_stage import BaseWorkflowStage
from conference_system.core.models import Author, Submission, SubmissionFile

from docx_processing.service import (
    extract_metadata,
    save_extracted_metadata,
    format_to_template,
)

DEFAULT_TEMPLATE_PATH = "samples/templates/conference_template_v1.docx"
DEFAULT_STORAGE_DIR = "storage/submissions"

# См. пункт B в docstring выше — черновые константы file_type,
# пока не вынесенные в общий core/file_types.py.
FILE_TYPE_ORIGINAL_DOCX = "original_docx"
FILE_TYPE_EXTRACTED_METADATA = "extracted_metadata"
FILE_TYPE_FORMATTED_DOCX = "formatted_docx"
FILE_TYPE_FORMATTING_REPORT = "formatting_report"


def _get_file_path(submission: Submission, file_type: str) -> str:
    for f in submission.files:
        if f.file_type == file_type:
            return f.path
    return ""


def _set_file_path(
        submission: Submission,
        file_type: str,
        path: str,
        mime_type: str = "",
) -> SubmissionFile:
    """Создаёт или обновляет запись SubmissionFile для данного file_type.

    submission_id + file_type уникальны (UniqueConstraint в models.py),
    поэтому при повторном запуске стадии (перезапуск обработки материала,
    ТЗ п.5.3 "перезапускать обработку материала") нужно ОБНОВЛЯТЬ
    существующую строку, а не пытаться вставить дубликат.
    """
    for f in submission.files:
        if f.file_type == file_type:
            f.path = path
            if mime_type:
                f.mime_type = mime_type
            return f
    new_file = SubmissionFile(
        submission_id=submission.submission_id,
        file_type=file_type,
        path=path,
        mime_type=mime_type,
    )
    submission.files.append(new_file)
    return new_file


def _submission_dir(submission: Submission, storage_dir: str) -> str:
    return os.path.join(storage_dir, submission.submission_id)


class ExtractMetadataStage(BaseWorkflowStage):
    """Workflow-этап "extract_metadata" (ТЗ п.10, п.20)."""

    stage_id = "extract_metadata"
    title = "Извлечение структуры материала"
    description = (
        "Читает original.docx, извлекает название, авторов, организацию, "
        "аннотацию, ключевые слова, текст, разделы, список литературы, "
        "таблицы, рисунки и формулы; сохраняет extracted_metadata.json."
    )
    enabled = True

    def __init__(self, storage_dir: str = DEFAULT_STORAGE_DIR):
        self.storage_dir = storage_dir

    def run(self, submission: Submission) -> dict[str, Any]:
        original_docx_path = _get_file_path(submission, FILE_TYPE_ORIGINAL_DOCX)
        if not original_docx_path:
            return {
                "status": "failed",
                "message": "В заявке не найден файл original_docx.",
                "warnings": ["В заявке не найден файл original_docx."],
            }

        metadata = extract_metadata(original_docx_path, submission_id=submission.submission_id)

        sub_dir = _submission_dir(submission, self.storage_dir)
        metadata_path = os.path.join(sub_dir, "extracted_metadata.json")
        save_extracted_metadata(metadata, metadata_path)
        _set_file_path(
            submission, FILE_TYPE_EXTRACTED_METADATA, metadata_path,
            mime_type="application/json",
        )

        # submission.metadata_json — присваиваем НОВЫЙ dict целиком
        # (см. пункт 3 в docstring модуля выше про JSON-колонки SQLAlchemy)
        submission.metadata_json = {
            **(submission.metadata_json or {}),
            "title_ru": metadata.get("title", ""),
            "title_en": metadata.get("title_en", ""),
            "authors_en": metadata.get("authors_en", []),  # см. пункт D
            "organization": metadata.get("organization", ""),
            "organization_en": metadata.get("organization_en", ""),
            "supervisor": metadata.get("supervisor", ""),
            "keywords_ru": metadata.get("keywords", []),
            "keywords_en": metadata.get("keywords_en", []),
            "abstract_ru": metadata.get("abstract", ""),
            "abstract_en": metadata.get("abstract_en", ""),
        }

        # authors — отдельная таблица models.Author, а не JSON (см. п.4)
        found_email = metadata.get("email", "")
        single_email = found_email.split(",")[0].strip() if found_email else ""
        submission.authors.clear()
        for i, full_name in enumerate(metadata.get("authors", [])):
            submission.authors.append(Author(
                submission_id=submission.submission_id,
                full_name=full_name,
                organization=metadata.get("organization", ""),
                email=single_email if i == 0 else "",
                role="author",
            ))

        warnings = metadata.get("warnings", [])
        if not metadata.get("body_text") and not metadata.get("title"):
            status = "failed"
        elif warnings:
            status = "warning"
        else:
            status = "success"

        return {
            "status": status,
            "message": "; ".join(warnings) if warnings else "Метаданные успешно извлечены.",
            "warnings": warnings,
            "extracted_metadata_path": metadata_path,
        }


class FormatToTemplateStage(BaseWorkflowStage):
    """Workflow-этап "format_to_template" (ТЗ п.10, п.21)."""

    stage_id = "format_to_template"
    title = "Приведение материала к шаблону конференции"
    description = (
        "Подставляет извлечённые данные в единый DOCX-шаблон конференции, "
        "переносит таблицы/рисунки/формулы, сохраняет formatted_material.docx "
        "и formatting_report.json."
    )
    enabled = True

    def __init__(
            self,
            template_path: str = DEFAULT_TEMPLATE_PATH,
            storage_dir: str = DEFAULT_STORAGE_DIR,
    ):
        # См. пункт A в docstring модуля — источник template_path пока не
        # закреплён в моделях ядра, поэтому это явный параметр стадии.
        self.template_path = template_path
        self.storage_dir = storage_dir

    def run(self, submission: Submission) -> dict[str, Any]:
        metadata_path = _get_file_path(submission, FILE_TYPE_EXTRACTED_METADATA)
        original_docx_path = _get_file_path(submission, FILE_TYPE_ORIGINAL_DOCX)

        if not metadata_path or not os.path.exists(metadata_path):
            message = (
                "Не найден extracted_metadata.json — стадия extract_metadata "
                "должна быть выполнена раньше."
            )
            return {"status": "failed", "message": message, "warnings": [message]}

        sub_dir = _submission_dir(submission, self.storage_dir)
        formatted_docx_path = os.path.join(sub_dir, "formatted_material.docx")
        report_path = os.path.join(sub_dir, "formatting_report.json")

        report = format_to_template(
            metadata_path,
            self.template_path,
            formatted_docx_path,
            output_report_path=report_path,
            original_docx_path=original_docx_path,
        )

        if report.get("output_docx"):
            _set_file_path(
                submission, FILE_TYPE_FORMATTED_DOCX, formatted_docx_path,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        _set_file_path(
            submission, FILE_TYPE_FORMATTING_REPORT, report_path,
            mime_type="application/json",
        )

        status = report.get("status", "failed")
        if status == "partial":
            status = "warning"

        warnings = report.get("warnings", [])
        return {
            "status": status,
            "message": "; ".join(warnings) if warnings else "Материал приведён к шаблону конференции.",
            "warnings": warnings,
            "formatted_docx_path": formatted_docx_path if report.get("output_docx") else "",
        }