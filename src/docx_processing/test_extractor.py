import json
import os
import sys
from typing import Any, Dict

from docx_processing.metadata_parser import MetadataParser
from docx_processing.formatter import MaterialFormatter


def main():
    # --- 1. Настройка входных и выходных файлов ---
    # Исходная статья автора и твой готовый шаблон
    input_docx_path = "algoritm_igas.docx"
    template_path = "conference_template_v1.docx"

    # Папка, куда сложим все итоговые артефакты
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    extracted_json_path = os.path.join(output_dir, "extracted_metadata.json")
    formatted_docx_path = os.path.join(output_dir, "formatted_material.docx")
    report_json_path = os.path.join(output_dir, "formatting_report.json")

    # --- 2. Проверка наличия исходных файлов на диске ---
    if not os.path.exists(input_docx_path):
        print(f"[ОШИБКА] Исходный файл '{input_docx_path}' не найден!", file=sys.stderr)
        return

    if not os.path.exists(template_path):
        print(f"[ОШИБКА] Файл шаблона '{template_path}' не найден!", file=sys.stderr)
        return

    # --- 3. Этап 1: Извлечение метаданных (MetadataParser) ---
    print(f"[1/3] Извлечение метаданных из '{input_docx_path}'...")
    try:
        parser = MetadataParser(input_docx_path)
        extracted_data: Dict[str, Any] = parser.parse()
    except Exception as e:
        print(f"[ОШИБКА] Критический сбой при парсинге метаданных: {e}", file=sys.stderr)
        return

    # Сохраняем промежуточный JSON с данными (согласно ТЗ и для удобства отладки)
    with open(extracted_json_path, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=2, ensure_ascii=False)
    print(f"      -> Метаданные сохранены: {extracted_json_path}")

    # --- 4. Этап 2: Приведение к шаблону (MaterialFormatter) ---
    print(f"[2/3] Подстановка данных в шаблон '{template_path}'...")
    formatter = MaterialFormatter(
        template_path=template_path,
        original_docx_path=input_docx_path  # Передаём статью, чтобы перенести из неё таблицы и рисунки
    )

    report = formatter.format_material(
        metadata=extracted_data,
        output_docx_path=formatted_docx_path,
        output_report_path=report_json_path
    )

    # --- 5. Этап 3: Вывод итоговой статистики ---
    print("[3/3] Обработка завершена!\n")
    print("--- Итоговый отчёт ---")
    print(f"Статус:          {report.get('status').upper()}")
    print(f"Заполнено полей: {len(report.get('filled_fields', []))} ({', '.join(report.get('filled_fields', []))})")

    missing = report.get("missing_fields", [])
    if missing:
        print(f"Пропущено полей: {len(missing)} ({', '.join(missing)})")
    else:
        print("Пропущено полей: 0 (Все 8 машинных полей успешно заполнены!)")

    warnings = report.get("warnings", [])
    if warnings:
        print("\nПредупреждения:")
        for w in warnings:
            print(f"  * {w}")

    print("----------------------")
    if report.get("status") in ["success", "partial"]:
        print(f"Готовый документ: {formatted_docx_path}")
        print(f"JSON-отчёт:       {report_json_path}")
    else:
        print(" Не удалось сформировать файл. Проверь предупреждения выше.")


if __name__ == "__main__":
    main()