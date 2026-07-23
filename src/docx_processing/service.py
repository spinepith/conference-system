"""
docx_processing.service — единая точка входа модуля для ОСТАЛЬНОЙ команды
проекта (ядро/студент 1, автоматические проверки/студент 4, редакторская
панель/студент 3, PDF-экспорт/студент 3).

Реализует workflow-этапы (ТЗ, раздел 10, WORKFLOW_STAGES):
    "extract_metadata"    -> extract_metadata() / save_extracted_metadata()
    "format_to_template"  -> format_to_template()

и удобную обёртку над обоими сразу — process_submission().

КАК ПОДКЛЮЧИТЬ МОДУЛЬ (для студента 1, ядро/workflow engine)
--------------------------------------------------------------
    from docx_processing.service import process_submission

    result = process_submission(
        original_docx_path=submission["files"]["original_docx"],
        template_path="samples/templates/conference_template_v1.docx",
        submission_id=submission["submission_id"],
    )

    submission["files"]["formatted_docx"] = result["files"]["formatted_docx"]
    if result["status"] == "failed":
        update_submission_status(submission_id, "error", comment="...")
    else:
        update_submission_status(submission_id, "formatted", comment="...")

Каждый шаг также доступен отдельно — например, если студент 4
(автоматические проверки) хочет получить только текст материала, не
дожидаясь форматирования:

    from docx_processing.service import extract_metadata
    metadata = extract_metadata(original_docx_path, submission_id)
    text_for_llm_check = metadata["body_text"]

Все функции модуля:
  * никогда не бросают исключения наружу;
  * возвращают только простые JSON-совместимые структуры (dict/list/str/
    int/float/bool/None) — результат можно напрямую сохранить через
    json.dump или отдать в БД студента 1 (BaseWorkflowStage.run(), ТЗ п.10);
  * не принимают и не возвращают объекты классов DocxExtractor /
    MetadataParser / TemplateEngine / MaterialFormatter — это внутренние
    детали реализации модуля docx_processing и в контракт не входят.
"""
import json
import os
from typing import Any, Dict, Optional, Union

from docx_processing.metadata_parser import extract_metadata as _extract_metadata
from docx_processing.formatter import format_to_template as _format_to_template

__all__ = [
    "extract_metadata",
    "save_extracted_metadata",
    "load_extracted_metadata",
    "format_to_template",
    "process_submission",
]


def extract_metadata(
        original_docx_path: str,
        submission_id: str = "temp_sub",
        storage_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Workflow-этап "extract_metadata" (ТЗ п.10). Контракт результата — ТЗ п.20.3.

    См. подробное описание полей в docx_processing/metadata_parser.py.
    """
    return _extract_metadata(
        original_docx_path,
        submission_id=submission_id,
        storage_dir=storage_dir,
    )


def save_extracted_metadata(metadata: Dict[str, Any], output_path: str) -> bool:
    """Сохраняет результат extract_metadata() в extracted_metadata.json (ТЗ п.8.1, п.14.2)."""
    try:
        target_dir = os.path.dirname(output_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return True
    except (OSError, TypeError, ValueError) as e:
        metadata.setdefault("warnings", []).append(
            f"Не удалось сохранить extracted_metadata.json: {e}"
        )
        return False


def load_extracted_metadata(json_path: str) -> Dict[str, Any]:
    """Читает ранее сохранённый extracted_metadata.json. Пустой dict при ошибке."""
    if not os.path.exists(json_path):
        return {}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[docx_processing.service] не удалось прочитать {json_path}: {e}")
        return {}


def format_to_template(
        extracted_metadata: Union[Dict[str, Any], str],
        template_path: str,
        output_docx_path: str,
        output_report_path: Optional[str] = None,
        original_docx_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Workflow-этап "format_to_template" (ТЗ п.10). Контракт результата — ТЗ п.21.4."""
    return _format_to_template(
        extracted_metadata,
        template_path,
        output_docx_path,
        output_report_path=output_report_path,
        original_docx_path=original_docx_path,
    )


def process_submission(
        original_docx_path: str,
        template_path: str,
        submission_id: str,
        storage_dir: str = "storage/submissions",
) -> Dict[str, Any]:
    """
    Выполняет оба этапа подряд ("extract_metadata" + "format_to_template")
    для одного материала и раскладывает результат по файлам ровно так,
    как описано в контракте Submission.files (ТЗ п.8.1):

        storage/submissions/<submission_id>/
            extracted_metadata.json
            formatted_material.docx
            formatting_report.json

    Returns
    -------
    dict:
        {
          "status": "success" | "partial" | "failed",
          "files": {
              "extracted_metadata": "storage/submissions/.../extracted_metadata.json",
              "formatted_docx": "storage/submissions/.../formatted_material.docx",  # "" при неудаче
              "formatting_report": "storage/submissions/.../formatting_report.json",
          },
          "metadata": {...},            # см. extract_metadata(), ТЗ п.20.3
          "formatting_report": {...},   # см. format_to_template(), ТЗ п.21.4
          "warnings": [...],            # объединённые предупреждения обоих этапов
        }

    Эта функция ничего не знает про базу данных / статусы заявки — это
    зона ответственности ядра (студент 1, core/workflow.py). Она только
    выполняет DOCX-обработку и возвращает пути к готовым файлам.
    """
    sub_dir = os.path.join(storage_dir, submission_id)
    os.makedirs(sub_dir, exist_ok=True)

    metadata_path = os.path.join(sub_dir, "extracted_metadata.json")
    formatted_docx_path = os.path.join(sub_dir, "formatted_material.docx")
    report_path = os.path.join(sub_dir, "formatting_report.json")

    metadata = extract_metadata(
        original_docx_path,
        submission_id=submission_id,
        storage_dir=storage_dir,
    )
    save_extracted_metadata(metadata, metadata_path)

    report = format_to_template(
        metadata,
        template_path,
        formatted_docx_path,
        output_report_path=report_path,
        original_docx_path=original_docx_path,
    )

    return {
        "status": report.get("status", "failed"),
        "files": {
            "extracted_metadata": metadata_path,
            "formatted_docx": formatted_docx_path if report.get("output_docx") else "",
            "formatting_report": report_path,
        },
        "metadata": metadata,
        "formatting_report": report,
        "warnings": list(dict.fromkeys(
            metadata.get("warnings", []) + report.get("warnings", [])
        )),
    }