"""
Внутренний низкоуровневый модуль. ТЗ, раздел 21 "Приведение материала к
шаблону конференции", п. 21.3 "Требования к шаблону".

ВНИМАНИЕ ДЛЯ ДРУГИХ РАЗРАБОТЧИКОВ ПРОЕКТА:
TemplateEngine — деталь реализации. Точка входа для интеграции —
docx_processing.service.format_to_template(...) / process_submission(...)
(см. service.py и README.md в корне модуля).

Соответствует ТЗ, п. 21.3 "Требования к шаблону": шаблон должен содержать
машинные поля вида {{ title_ru }}, {{ authors }}, {{ organization }},
{{ supervisor }}, {{ abstract_ru }}, {{ keywords_ru }}, {{ body_text }},
{{ references }}.

Используется библиотека docxtpl (обёртка над python-docx + Jinja2),
рекомендованная в ТЗ, раздел 9 "Архитектура системы".

Установка зависимости:
    pip install docxtpl
"""
import os
from typing import Any, Dict, List, Optional
from docxtpl import DocxTemplate


# ---------------------------------------------------------------------------
# Требования к оформлению материала конференции (ТЗ, раздел 15
# "Шаблон конференционного материала" и файл-образец оформления доклада).
# Используются при генерации самого файла шаблона (build_template.py,
# отдельный вспомогательный скрипт вне контракта пайплайна) и как единый
# источник правды, если потребуется где-то ещё проверить соответствие
# документа этим требованиям (например, в модуле "проверка качества
# оформления" студента 4, ТЗ п. 11.6).
# ---------------------------------------------------------------------------
TEMPLATE_STYLE_SPEC: Dict[str, Any] = {
    # 1. Параметры страницы и поля
    "page_size": "A4",
    "margins_mm": {"top": 25, "bottom": 25, "left": 25, "right": 25},

    # 2. Основной текст и абзацы
    "font_name": "Times New Roman",
    "font_size_pt": 12,
    "line_spacing_multiple": 1.2,  # межстрочное расстояние — множитель 1,2
    "first_line_indent_cm": 0.75,  # абзацный отступ 0,75 см
    "hyphenation_enabled": False,  # расстановка переносов — НЕТ
    "body_alignment": "justify",  # выравнивание текста по ширине

    # 3. Заголовки
    "title_font_size_pt": 12,  # кегль заголовка — 12 пт
    "title_bold": True,  # заголовок ОБЯЗАТЕЛЬНО жирный

    # 4. Требования к объектам (таблицы и рисунки)
    "objects_spec": {
        "inline_placement": True,  # вставляются прямо в текст доклада
        "require_numbering": True,  # обязательно нумеруются (Рис. 1, Таблица 1)
        "require_captions": True,  # обязательно подписываются
        "group_word_drawings": True,  # фигуры Word должны быть сгруппированы
    },

    # 5. Математический редактор формул
    "formula_editor_font": "Times New Roman",
    "formula_sizes_pt": {
        "normal": 12,  # обычный – 12 pt
        "large_index": 8,  # крупный индекс – 8 pt
        "small_index": 6,  # мелкий индекс – 6 pt
        "large_symbol": 18,  # крупный символ – 18 pt
        "small_symbol": 10,  # мелкий символ – 10 pt
    },

    # 6. Библиография
    "references_style": "ГОСТ 7.1-2003",
}


class TemplateEngine:
    """
    Отвечает ТОЛЬКО за механику рендеринга (загрузка шаблона, подстановка
    контекста, сохранение результата) — никакой бизнес-логики о том, откуда
    берутся данные и как их готовить к подстановке. Эта логика вынесена в
    MaterialFormatter (см. formatter.py), который использует TemplateEngine
    как инструмент.

    Инвариант класса: методы load_template() -> render() -> save() должны
    вызываться строго в этом порядке (это отражено в докстрингах ниже —
    каждый следующий метод при необходимости подтягивает предыдущий шаг
    сам, но лучше вызывать явно и проверять возвращаемый bool).
    """

    def __init__(self, template_path: str):
        """
        Parameters
        ----------
        template_path : str
            Путь к DOCX-файлу шаблона конференции, например
            "samples/templates/conference_template_v1.docx".
        """
        self.template_path = template_path
        self.warnings: List[str] = []
        self._tpl: Optional[DocxTemplate] = None
        self._rendered: bool = False

    def load_template(self) -> bool:
        """
        Загружает DOCX-шаблон в память.
        """
        if not os.path.exists(self.template_path):
            self.warnings.append(f"Шаблон не найден: {self.template_path}")
            return False

        try:
            self._tpl = DocxTemplate(self.template_path)
            return True
        except Exception as e:
            self.warnings.append(f"Ошибка при загрузке шаблона '{self.template_path}': {str(e)}")
            return False

    def get_template_variables(self) -> List[str]:
        """
        Возвращает отсортированный список имён всех переменных {{ ... }},
        реально присутствующих в шаблоне.
        """
        if self._tpl is None:
            if not self.load_template():
                return []

        try:
            variables = self._tpl.get_undeclared_template_variables()
            return sorted(list(variables))
        except Exception as e:
            self.warnings.append(f"Не удалось извлечь переменные из шаблона: {str(e)}")
            return []

    def render(self, context: Dict[str, Any]) -> bool:
        """
        Подставляет данные из context в загруженный шаблон.
        """
        if self._tpl is None:
            if not self.load_template():
                return False

        try:
            self._tpl.render(context)
            self._rendered = True
            return True
        except Exception as e:
            self.warnings.append(f"Ошибка при рендеринге шаблона: {str(e)}")
            return False

    def save(self, output_path: str) -> bool:
        """
        Сохраняет отрендеренный документ на диск.
        """
        if self._tpl is None or not self._rendered:
            self.warnings.append("Попытка сохранить нерендеренный шаблон")
            return False

        try:
            target_dir = os.path.dirname(output_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            self._tpl.save(output_path)
            return True
        except Exception as e:
            self.warnings.append(f"Ошибка при сохранении документа в '{output_path}': {str(e)}")
            return False