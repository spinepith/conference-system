"""Разовый прогон модуля для визуальной проверки результата."""
import shutil
from pathlib import Path

from result_export.service import finalize_submission_files

# Готовим тестовую "заявку" в отдельной папке рядом с проектом
submission_dir = Path("demo_output/SUB-DEMO-0001")
submission_dir.mkdir(parents=True, exist_ok=True)

# Копируем тестовый DOCX как formatted_material.docx
shutil.copy(
    "samples/input_materials/sample_formatted_material.docx",
    submission_dir / "formatted_material.docx",
)

# Запускаем весь модуль: PDF-экспорт + реестр + ZIP
report = finalize_submission_files(submission_dir)

print("Статус:", report["status"])
print("Ошибка:", report.get("error"))
print("Файлы теперь лежат в:", submission_dir.resolve())