"""
ТЗ, раздел 20 "DOCX-извлечение и анализ структуры материала".

ПУБЛИЧНЫЙ КОНТРАКТ ДЛЯ ДРУГИХ РАЗРАБОТЧИКОВ (ТЗ, п. 20.3)
-----------------------------------------------------------------
extract_metadata(file_path, submission_id) -> dict со следующими
ОБЯЗАТЕЛЬНЫМИ полями (порядок и типы соответствуют примеру из ТЗ):

    {
      "title": str,
      "authors": [str, ...],
      "organization": str,
      "abstract": str,
      "keywords": [str, ...],
      "body_text": str,
      "sections": [{"title": str, "text": str}, ...],
      "references": [str, ...],
      "objects": {
          "tables_count": int,
          "figures_count": int,
          "equations_count": int
      },
      "warnings": [str, ...]
    }

Модуль НИКОГДА не бросает исключение наружу и не "падает" на плохом
файле (требование ТЗ, п. 20.6 "при ошибке не падает"): любые проблемы
извлечения попадают строкой в metadata["warnings"].

ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ (не входят в обязательный контракт 20.3, но нужны
другим модулям того же пайплайна и НЕ должны ломать код, который читает
только обязательные поля):

    "udc"                 — УДК, если найден;
    "title_en", "authors_en", "organization_en", "abstract_en",
    "keywords_en"         — англоязычные версии полей (ТЗ, п.15);
    "email"                — e-mail(ы) контактного автора, через запятую;
    "supervisor"           — научный руководитель;
    "objects.structured_tables",
    "objects.saved_images",
    "objects.extracted_equations"
                            — служебные данные для повторной сборки
                              документа модулем docx_processing.formatter
                              (переноса таблиц/рисунков/формул при
                              приведении к шаблону, ТЗ п.21). Другие
                              модули (проверки, редакторская панель и
                              т.п.) эти поля использовать не должны —
                              они специфичны для внутренней связки
                              extractor -> formatter через токены вида
                              [[TABLE_1]], [[IMAGE_1]], [[EQUATION_1]].

ВАЖНО (расхождение внутри самого ТЗ): в разделе 8.1 "Submission" поле
metadata.authors — список ОБЪЕКТОВ {full_name, organization, email}, а
в разделе 20.3 (формат результата именно этого модуля) authors — список
СТРОК. Данный модуль реализует буквально п. 20.3 (список строк), так как
это спецификация именно модуля извлечения. Преобразование в формат
Submission (объекты автора) — задача сервиса заявок студента 1 при
записи заявки в базу; при необходимости можно склеить authors (список
ФИО) с organization (общая на всех авторов строка) на стороне ядра.
"""
import os
import re
from typing import Any, Dict, List, Optional
from docx_processing.extractor import DocxExtractor

# Обязательные по контракту 20.3 поля верхнего уровня и их "пустые" значения.
# Используются как страховка, если формат результата когда-нибудь поменяется.
_CONTRACT_DEFAULTS: Dict[str, Any] = {
    "title": "",
    "authors": [],
    "organization": "",
    "abstract": "",
    "keywords": [],
    "body_text": "",
    "sections": [],
    "references": [],
    "objects": {"tables_count": 0, "figures_count": 0, "equations_count": 0},
    "warnings": [],
}


class MetadataParser:
    """Внутренняя реализация анализа структуры документа.

    Снаружи модуля рекомендуется использовать функцию extract_metadata()
    ниже, а не создавать MetadataParser напрямую — так интерфейс модуля
    останется стабильным, даже если внутренняя реализация изменится.
    """

    PATTERNS = {
        "email": r"[\w.\-]+[ \t\u00A0]?@[ \t\u00A0]?[\w.\-]+\.\w+",
        "udc": r"^УДК\s+([0-9\.\-\+:\/\s]+)",
        "supervisor": r"(?:Научный\s+руководитель|Руководитель)\s*:?\s*([^\n]+)",
        "ref_start": r"^(?:\d+[\.\)\s]*)?(?:Список\s+(?:литературы|использованных\s+источников)|Библиографический\s+список|References|Литература)\s*[:.]?\s*$",
        "section_header": r"^(?:\d+(?:\.\d+)*\.\s+[А-ЯA-Z][^\n]{0,78}|(?:Введение|Методы|Результаты|Обсуждение|Заключение|Выводы|Постановка\s+задачи)\s*[:.]?\s*)$",
        "author_initials": r"[А-ЯA-Z]\.\s*[А-ЯA-Z]\.",
        "org_keywords": r"университет|институт|академия|россия|беларусь|кафедра|факультет|г\.",
    }

    def __init__(
        self,
        file_path: str,
        submission_id: str = "temp_sub",
        storage_dir: Optional[str] = None,
    ):
        self.file_path = file_path
        self.submission_id = submission_id
        image_storage_dir = (
            os.path.join(storage_dir, submission_id, "images")
            if storage_dir
            else None
        )
        self.extractor = DocxExtractor(file_path, image_storage_dir=image_storage_dir)
        self.raw_data = self.extractor.extract_raw_data(submission_id=self.submission_id)
        self.warnings: List[str] = self.raw_data.get("warnings", [])

    def _clean_text(self, text: str) -> str:
        lines = [re.sub(r"[ \t\u00A0]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)

    def _extract_by_regex(self, text: str, pattern_key: str, flags: int = re.IGNORECASE) -> str:
        match = re.search(self.PATTERNS[pattern_key], text, flags)
        return match.group(1).strip() if match else ""

    def _parse_references(self, ref_lines: List[str]) -> List[str]:
        cleaned = [re.sub(r"^\d+[\.\)\s]+", "", line).strip() for line in ref_lines]
        return [ref for ref in cleaned if len(ref) > 10 and not ref.endswith(":")]

    def _is_mostly_cyrillic(self, line: str) -> bool:
        cyr, lat = len(re.findall(r"[А-Яа-яЁё]", line)), len(re.findall(r"[A-Za-z]", line))
        return True if cyr == 0 and lat == 0 else cyr >= lat

    def _dedup_keep_order(self, items: List[str]) -> List[str]:
        return list(dict.fromkeys(items))

    def _parse_header_block(self, header_lines: List[str]) -> Dict[str, Any]:
        valid_lines = [l for l in header_lines if not re.search(r"^УДК|@|e-mail|поступила|рецензирование|формат\s+листа|(?:Научный\s+руководитель|Руководитель)\s*:?", l, re.IGNORECASE)]
        author_lines = [l for l in valid_lines if re.search(self.PATTERNS["author_initials"], l)]

        def _split_authors(lines: List[str]) -> List[str]:
            result = []
            for line in lines:
                for part in re.sub(r"(?<=[А-ЯA-Z]\.)\s*\d+", "", line).split(","):
                    if part.strip() and re.search(r"[А-Яа-яA-Za-z]", part):
                        result.append(part.strip())
            return self._dedup_keep_order(result)

        authors = _split_authors([l for l in author_lines if self._is_mostly_cyrillic(l)])
        authors_en = _split_authors([l for l in author_lines if not self._is_mostly_cyrillic(l)])
        org_lines = [l for l in valid_lines if re.search(self.PATTERNS["org_keywords"], l, re.IGNORECASE)]

        def _clean_org(lines: List[str]) -> str:
            return "; ".join(self._dedup_keep_order([re.sub(r"^\d+\s*", "", org).strip() for org in lines]))

        organization = _clean_org([l for l in org_lines if self._is_mostly_cyrillic(l)])
        organization_en = _clean_org([l for l in org_lines if not self._is_mostly_cyrillic(l)])
        title_lines = [l for l in valid_lines if l.isupper() and len(l) > 5 and l not in author_lines and l not in org_lines]
        title = " ".join([l for l in title_lines if self._is_mostly_cyrillic(l)]).strip()
        title_en = " ".join([l for l in title_lines if not self._is_mostly_cyrillic(l)]).strip()
        if not title and not title_en and valid_lines:
            title = valid_lines[0]

        return {"title": title, "title_en": title_en, "authors": authors, "authors_en": authors_en, "organization": organization, "organization_en": organization_en}

    def _parse_sections(self, body_lines: List[str]) -> List[Dict[str, str]]:
        sections, current_title, current_text = [], "Общий раздел", []
        for line in body_lines:
            if re.match(self.PATTERNS["section_header"], line, re.IGNORECASE) and len(line) < 80:
                if not line.endswith(";") and not (line.endswith(":") and not any(k in line.lower() for k in ["введение", "выводы", "заключение"])):
                    if current_text:
                        sections.append({"title": current_title, "text": "\n\n".join(current_text)})
                    current_title, current_text = line, []
                    continue
            current_text.append(line)
        if current_text:
            sections.append({"title": current_title, "text": "\n\n".join(current_text)})
        return sections

    def parse(self) -> Dict[str, Any]:
        """Возвращает словарь по контракту ТЗ п.20.3 (+ доп. поля, см. docstring модуля)."""
        raw_blocks = self.raw_data.get("ordered_blocks", [])
        lines = [self._clean_text(b["text"]) for b in raw_blocks if b["text"].strip()]

        result: Dict[str, Any] = {
            "udc": "", "title": "", "title_en": "", "authors": [], "authors_en": [],
            "organization": "", "organization_en": "", "email": "", "supervisor": "",
            "abstract": "", "abstract_en": "", "keywords": [], "keywords_en": [],
            "body_text": "", "sections": [], "references": [],
            "objects": {
                "tables_count": self.raw_data.get("tables_count", 0),
                "figures_count": self.raw_data.get("figures_count", 0),
                "equations_count": self.raw_data.get("equations_count", 0),
                # служебные данные для formatter.py, см. docstring модуля выше
                "saved_images": self.raw_data.get("saved_images", []),
                "structured_tables": self.raw_data.get("structured_tables", []),
                "extracted_equations": self.raw_data.get("extracted_equations", {}),
            },
            "warnings": self.warnings,
        }

        if not lines:
            self.warnings.append("Документ пуст или не содержит распознаваемого текста.")
            return result

        full_text = "\n".join(lines)
        emails = re.findall(self.PATTERNS["email"], full_text)
        result["email"] = ", ".join(self._dedup_keep_order([re.sub(r"[ \t\u00A0]", "", e) for e in emails]))
        result["udc"] = self._extract_by_regex(full_text, "udc", re.MULTILINE | re.IGNORECASE)
        result["supervisor"] = self._extract_by_regex(full_text, "supervisor")

        raw_keywords_ru, raw_keywords_en = "", ""
        for line in lines:
            m = re.match(r"^Аннотация\s*[:.]\s*(.+)", line, re.IGNORECASE)
            if m and not result["abstract"]:
                result["abstract"] = m.group(1).strip(); continue
            m = re.match(r"^Abstract\s*[:.]\s*(.+)", line, re.IGNORECASE)
            if m and not result["abstract_en"]:
                result["abstract_en"] = m.group(1).strip(); continue
            m = re.match(r"^Ключевые\s+слова\s*[:.]\s*(.+)", line, re.IGNORECASE)
            if m and not raw_keywords_ru:
                raw_keywords_ru = m.group(1).strip(); continue
            m = re.match(r"^Keywords\s*[:.]\s*(.+)", line, re.IGNORECASE)
            if m and not raw_keywords_en:
                raw_keywords_en = m.group(1).strip(); continue

        result["keywords"] = [kw.strip(". ") for kw in re.split(r"[,;]", raw_keywords_ru) if kw.strip()]
        result["keywords_en"] = [kw.strip(". ") for kw in re.split(r"[,;]", raw_keywords_en) if kw.strip()]

        if not result["email"]: self.warnings.append("E-mail контактного автора не найден.")
        if not result["abstract"]: self.warnings.append("Аннотация не найдена в исходном файле.")
        if not result["keywords"]: self.warnings.append("Ключевые слова не найдены.")

        ref_idx = next((i for i, line in enumerate(lines) if re.match(self.PATTERNS["ref_start"], line, re.IGNORECASE)), len(lines))
        content_lines, reference_lines = lines[:ref_idx], lines[ref_idx + 1:]
        result["references"] = self._parse_references(reference_lines)
        if not result["references"] and ref_idx != len(lines):
            self.warnings.append("Список литературы пуст или не удалось распознать источники.")

        header_idx = next((i for i, line in enumerate(content_lines) if re.match(r"^(?:Аннотация|Abstract|Ключевые)", line, re.IGNORECASE)), min(5, len(content_lines)))
        result.update(self._parse_header_block(content_lines[:header_idx]))
        if not result["title"]: self.warnings.append("Название статьи не удалось определить автоматически.")

        if result["supervisor"]:
            org_match = re.search(r"([А-ЯЁ][\w\-]*(?:\s+[А-ЯЁ][\w\-]*){0,5}\s+(?:университет|институт|академия)\w*.*)$", result["supervisor"], re.IGNORECASE)
            if org_match:
                found_org = org_match.group(1).strip()
                if not result["organization"]: result["organization"] = found_org
                result["supervisor"] = result["supervisor"].replace(found_org, "").strip(",. ")

        if not result["organization"]: self.warnings.append("Организация не найдена автоматически.")

        body_lines = [
            line for line in content_lines[header_idx:]
            if not re.match(r"^(?:Аннотация|Abstract|Ключевые\s+слова|Keywords)", line, re.IGNORECASE)
            and not re.match(self.PATTERNS["ref_start"], line, re.IGNORECASE)
            and line not in (result["abstract"], result["abstract_en"], raw_keywords_ru, raw_keywords_en)
        ]
        result["sections"] = self._parse_sections(body_lines)
        result["body_text"] = "\n\n".join(body_lines)
        return result


def extract_metadata(
    file_path: str,
    submission_id: str = "temp_sub",
    storage_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ЕДИНСТВЕННАЯ рекомендуемая точка входа модуля для остальных
    разработчиков проекта (workflow-этап "extract_metadata", ТЗ п.10).

    Parameters
    ----------
    file_path : str
        Путь к исходному DOCX-файлу автора (files.original_docx, ТЗ п.8.1).
    submission_id : str
        Идентификатор заявки (submission_id, ТЗ п.8.1) — используется как
        префикс для файлов извлечённых изображений в
        storage/submissions/<submission_id>/images/.

    Returns
    -------
    dict — контракт ТЗ п.20.3 (+ доп. поля, см. docstring модуля).
    Функция никогда не бросает исключения; при сбое возвращает словарь с
    пустыми полями и описанием проблемы в metadata["warnings"].
    """
    try:
        parser = MetadataParser(
            file_path,
            submission_id=submission_id,
            storage_dir=storage_dir,
        )
        metadata = parser.parse()
    except Exception as e:
        metadata = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in _CONTRACT_DEFAULTS.items()}
        metadata["warnings"].append(f"Непредвиденная ошибка извлечения метаданных: {e}")
        return metadata

    for field, default in _CONTRACT_DEFAULTS.items():
        metadata.setdefault(field, default.copy() if isinstance(default, (list, dict)) else default)
    return metadata