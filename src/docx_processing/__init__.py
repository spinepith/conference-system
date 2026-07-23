"""
Пакет docx_processing — реализация заданий студента 2 ("DOCX-извлечение и
анализ структуры материала", ТЗ п.20) и студента 2.доп ("Приведение
материала к шаблону конференции", ТЗ п.21).

Для интеграции с остальными частями системы используйте ТОЛЬКО функции,
реэкспортированные ниже (они же определены в docx_processing.service).
Подробное описание контракта данных и примеры — в README.md рядом с этим
файлом.
"""
from docx_processing.service import (
    extract_metadata,
    save_extracted_metadata,
    load_extracted_metadata,
    format_to_template,
    process_submission,
)

__all__ = [
    "extract_metadata",
    "save_extracted_metadata",
    "load_extracted_metadata",
    "format_to_template",
    "process_submission",
]