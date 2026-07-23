"""
ТЗ, раздел 21 "Приведение материала к шаблону конференции".

ПУБЛИЧНЫЙ КОНТРАКТ ДЛЯ ДРУГИХ РАЗРАБОТЧИКОВ (ТЗ, п. 21.4)
-----------------------------------------------------------------
format_to_template(...) -> dict со следующими ОБЯЗАТЕЛЬНЫМИ полями
(formatting_report.json, пример из ТЗ):

    {
      "status": "success" | "partial" | "failed",
      "template_used": str,
      "filled_fields": [str, ...],
      "missing_fields": [str, ...],
      "warnings": [str, ...],
      "output_docx": str
    }

Вход функции — либо словарь, полученный от
docx_processing.metadata_parser.extract_metadata() (контракт ТЗ п.20.3),
либо путь к сохранённому на диске extracted_metadata.json.

Модуль не бросает исключений наружу: любая ошибка (отсутствие шаблона,
битый DOCX, сбой рендера) отражается в report["status"] == "failed" и
report["warnings"], как того требует ТЗ п.34 "Ошибки должны сохраняться
в отчёте и отображаться пользователю понятным языком".
"""
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Union
import docx
from docx.oxml import parse_xml
from docx.shared import Cm, Emu, Inches, Pt
from docx.table import Table
from docx_processing.extractor import DocxExtractor
from docx_processing.template_engine import TemplateEngine, TEMPLATE_STYLE_SPEC


class MaterialFormatter:
    """Высокоуровневый оркестратор приведения материала к шаблону (ТЗ, п. 21).

    Снаружи модуля рекомендуется использовать функцию
    format_to_template() (ниже) вместо прямого создания MaterialFormatter.
    """

    # Соответствие полей шаблона (ТЗ п.21.3, {{ ... }} в DOCX-шаблоне)
    # полям extracted_metadata.json (ТЗ п.20.3).
    TEMPLATE_FIELD_MAP: Dict[str, str] = {
        "title_ru": "title",
        "authors": "authors",
        "organization": "organization",
        "supervisor": "supervisor",
        "abstract_ru": "abstract",
        "keywords_ru": "keywords",
        "body_text": "body_text",
        "references": "references",
    }

    def __init__(
            self, template_path: str, original_docx_path: Optional[str] = None
    ):
        self.template_path = template_path
        self.original_docx_path = original_docx_path
        self.engine = TemplateEngine(template_path)
        self.warnings: List[str] = []
        self.filled_fields: List[str] = []
        self.missing_fields: List[str] = []

    @staticmethod
    def load_extracted_metadata(json_path: str) -> Dict[str, Any]:
        if not os.path.exists(json_path):
            return {}
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError) as e:
            print(
                f"[Ошибка] Не удалось загрузить метаданные из {json_path}: {e}",
                file=sys.stderr,
            )
            return {}

    def _build_context(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        context: Dict[str, Any] = {}

        for template_field, metadata_field in self.TEMPLATE_FIELD_MAP.items():
            value = metadata.get(metadata_field)
            str_val = ""

            if metadata_field == "authors" and isinstance(value, list):
                str_val = ", ".join(str(item) for item in value if item is not None)
            elif metadata_field == "keywords" and isinstance(value, list):
                str_val = ", ".join(str(item) for item in value if item is not None)
            elif metadata_field == "references" and isinstance(value, list):
                str_val = "\n\n".join(
                    f"{i + 1}. {ref}" for i, ref in enumerate(value) if ref is not None
                )
            else:
                if isinstance(value, str):
                    str_val = value
                elif value is not None:
                    str_val = str(value)

            if not str_val.strip():
                self.missing_fields.append(template_field)
                context[template_field] = ""
                if template_field == "abstract_ru":
                    self.warnings.append("Аннотация не найдена в исходном файле.")
                elif template_field == "keywords_ru":
                    self.warnings.append("Ключевые слова не найдены в исходном файле.")
            else:
                self.filled_fields.append(template_field)
                context[template_field] = str_val

        return context

    def _restore_paragraphs_and_breaks(self, output_docx_path: str):
        try:
            doc = docx.Document(output_docx_path)
            paragraphs_to_remove = []
            for p in list(doc.paragraphs):
                if "\n\n" in p.text:
                    parts = [
                        part.strip() for part in p.text.split("\n\n") if part.strip()
                    ]
                    if parts:
                        for part in parts:
                            p.insert_paragraph_before(part, style=p.style)
                        paragraphs_to_remove.append(p)
                elif "\n" in p.text:
                    parts = p.text.split("\n")
                    p.text = parts[0]
                    for part in parts[1:]:
                        run = p.add_run()
                        run.add_break()
                        run = p.add_run(part)
            for p in paragraphs_to_remove:
                p._p.getparent().remove(p._p)
            doc.save(output_docx_path)
        except Exception as e:
            self.warnings.append(f"Ошибка при восстановлении абзацев: {e}")

    def _enforce_table_font(self, table: "docx.table.Table"):
        """Принудительно приводит шрифт всех ячеек таблицы к требованиям
        шаблона конференции (ТЗ п.11.6 "Шрифт в таблицах должен быть 12 пт",
        см. также TEMPLATE_STYLE_SPEC в template_engine.py).

        Нужен ОТДЕЛЬНО от простановки шрифта при ручной сборке таблицы
        (см. ниже), потому что при переносе таблицы через прямую
        XML-инъекцию (основной путь _transfer_tables) в документ копируется
        весь исходный XML таблицы автора as-is, включая её родное
        форматирование (например, кегль 14 вместо требуемых 12) — и без
        этого шага оно так и оставалось бы неисправленным.
        """
        font_name = TEMPLATE_STYLE_SPEC["font_name"]
        font_size = Pt(TEMPLATE_STYLE_SPEC["font_size_pt"])
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.name = font_name
                        run.font.size = font_size
                        # Явно задаём и восточноазиатский/сложный шрифт в
                        # rPr рядом с ascii/hAnsi — иначе кириллица может
                        # унаследовать другой размер из исходного w:rFonts,
                        # если он был прописан отдельно для eastAsia/cs.
                        rPr = run._element.get_or_add_rPr()
                        rFonts = rPr.find(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts"
                        )
                        if rFonts is not None:
                            for attr in ("eastAsia", "cs"):
                                key = f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{attr}"
                                if rFonts.get(key):
                                    rFonts.set(key, font_name)

    def _transfer_tables(
            self,
            output_docx_path: str,
            metadata: Optional[Dict[str, Any]] = None,
    ):
        try:
            tables_data = (
                metadata.get("objects", {}).get("structured_tables", [])
                if metadata
                else []
            )
            if not tables_data:
                return

            doc = docx.Document(output_docx_path)
            for p in list(doc.paragraphs):
                match = re.search(r"\[\[TABLE_(\d+)\]\]", p.text)
                if match:
                    table_idx = int(match.group(1)) - 1
                    if 0 <= table_idx < len(tables_data):
                        table_info = tables_data[table_idx]
                        p.text = ""
                        if "xml" in table_info and table_info["xml"]:
                            try:
                                injected_tbl_elem = parse_xml(table_info["xml"])
                                p._p.addprevious(injected_tbl_elem)
                                p._p.getparent().remove(p._p)
                                self._enforce_table_font(Table(injected_tbl_elem, doc))
                                continue
                            except Exception as e:
                                self.warnings.append(
                                    f"Сбой XML-инъекции таблицы {table_idx + 1}: {e}"
                                )

                        rows_data = table_info.get("rows", [])
                        if rows_data:
                            rows_cnt, cols_cnt = (
                                len(rows_data),
                                len(rows_data[0]) if rows_data else 0,
                            )
                            if rows_cnt > 0 and cols_cnt > 0:
                                new_table = doc.add_table(rows=rows_cnt, cols=cols_cnt)
                                new_table.style = "Table Grid"
                                for r_idx, row_cells in enumerate(rows_data):
                                    for c_idx, cell_value in enumerate(row_cells):
                                        cell = new_table.cell(r_idx, c_idx)
                                        cell.text = str(cell_value).strip()
                                        for paragraph in cell.paragraphs:
                                            paragraph.paragraph_format.space_after = Pt(2)
                                            paragraph.paragraph_format.space_before = Pt(2)
                                self._enforce_table_font(new_table)
                                p._p.addprevious(new_table._tbl)
                                p._p.getparent().remove(p._p)
            doc.save(output_docx_path)
        except Exception as e:
            self.warnings.append(f"Ошибка при переносе таблиц: {str(e)}")

    def _transfer_figures(
            self,
            output_docx_path: str,
            metadata: Optional[Dict[str, Any]] = None,
    ):
        try:
            images_data = (
                metadata.get("objects", {}).get("saved_images", [])
                if metadata
                else []
            )
            if not images_data:
                return

            doc = docx.Document(output_docx_path)
            for p in list(doc.paragraphs):
                match = re.search(r"\[\[IMAGE_(\d+)\]\]", p.text)
                if match:
                    img_idx = int(match.group(1)) - 1
                    found_path = None
                    width_emu = None
                    height_emu = None

                    if 0 <= img_idx < len(images_data):
                        img_info = images_data[img_idx]
                        width_emu = img_info.get("width_emu")
                        height_emu = img_info.get("height_emu")

                        submission_id = os.path.basename(
                            os.path.dirname(self.original_docx_path or "")
                        ) or "temp_sub"
                        test_paths = [
                            img_info.get("file_path", ""),
                            os.path.join(
                                f"storage/submissions/{submission_id}/images",
                                img_info.get("file_name", ""),
                            ),
                            os.path.join(
                                "images", img_info.get("file_name", "")
                            ),
                        ]
                        for path in test_paths:
                            if path and os.path.exists(path):
                                found_path = path
                                break

                    if found_path:
                        p.text = p.text.replace(f"[[IMAGE_{img_idx + 1}]]", "").strip()
                        run = p.add_run()

                        try:
                            if width_emu and height_emu and int(width_emu) > 0 and int(height_emu) > 0:
                                run.add_picture(
                                    found_path,
                                    width=Emu(int(width_emu)),
                                    height=Emu(int(height_emu)),
                                )
                            else:
                                try:
                                    from PIL import Image
                                    with Image.open(found_path) as img:
                                        width_px, _ = img.size
                                        if width_px > 500:
                                            run.add_picture(found_path, width=Inches(5.5))
                                        else:
                                            run.add_picture(found_path)
                                except Exception:
                                    run.add_picture(found_path)
                        except Exception as pic_e:
                            self.warnings.append(f"Ошибка вставки графики [[IMAGE_{img_idx + 1}]]: {pic_e}")

                        p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
                    else:
                        self.warnings.append(
                            f"Файл для [[IMAGE_{img_idx + 1}]] не найден на диске."
                        )
            doc.save(output_docx_path)
        except Exception as e:
            self.warnings.append(f"Ошибка при переносе изображений: {str(e)}")

    def _transfer_equations(
            self,
            output_docx_path: str,
            metadata: Optional[Dict[str, Any]] = None,
    ):
        try:
            equations_map = (
                metadata.get("objects", {}).get("extracted_equations", {})
                if metadata
                else {}
            )
            if not equations_map:
                return

            doc = docx.Document(output_docx_path)
            for p in list(doc.paragraphs):
                tokens = re.findall(r"\[\[EQUATION_\d+\]\]", p.text)
                for token in tokens:
                    if token in equations_map:
                        try:
                            num_match = re.search(r"\(\d+(?:\.\d+)*\)", p.text)
                            eq_num_str = f"\t{num_match.group(0)}" if num_match else ""

                            p.text = ""

                            p._p.append(parse_xml(equations_map[token]))

                            if eq_num_str:
                                run = p.add_run(eq_num_str)
                                run.font.name = "Times New Roman"
                                run.font.size = Pt(12)

                            p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
                        except Exception as e:
                            self.warnings.append(f"Ошибка вставки формулы {token}: {e}")
            doc.save(output_docx_path)
        except Exception as e:
            self.warnings.append(f"Ошибка при переносе формул: {str(e)}")

    # Заголовок списка литературы (см. _fix_references_heading_position)
    _REFERENCES_HEADING_RE = re.compile(
        r"^(?:Список\s+(?:литературы|использованных\s+источников)"
        r"|Библиографический\s+список|References)\s*[:.]?\s*$",
        re.IGNORECASE,
    )
    _REFERENCE_ITEM_RE = re.compile(r"^\d+[\.\)]\s+\S")

    def _fix_references_heading_position(self, docx_path: str):
        """Чинит расположение заголовка списка литературы в итоговом
        документе.

        Причина бага: заголовок вида "Список использованных источников" —
        это СТАТИЧНЫЙ текст в самом DOCX-шаблоне конференции (не
        подставляется кодом), а поле {{ references }} рендерится строго
        отдельно (см. _build_context) как пронумерованный список без
        какого-либо заголовка (ТЗ п.20.3/21.3 не требуют заголовка внутри
        самого значения поля — предполагается, что заголовок в шаблоне
        должен стоять НАД полем). Если в шаблоне заголовок по ошибке
        размещён НИЖЕ параграфа с {{ references }}, он проваливается под
        весь пронумерованный список после подстановки данных.

        Метод находит первый параграф пронумерованного списка литературы
        и, если заголовок стоит не сразу перед ним (в частности — вообще
        ниже списка), физически переносит параграф с заголовком на нужное
        место. Правка шаблона (перестановка параграфов в самом .docx)
        решила бы то же самое раз и навсегда, но этот шаг подстраховывает
        результат независимо от того, поправят шаблон или нет.
        """
        try:
            doc = docx.Document(docx_path)
            paragraphs = doc.paragraphs

            first_ref_idx = next(
                (i for i, p in enumerate(paragraphs)
                 if self._REFERENCE_ITEM_RE.match(p.text.strip())),
                None,
            )
            if first_ref_idx is None:
                return  # пронумерованного списка литературы нет — чинить нечего

            heading_idx = next(
                (i for i, p in enumerate(paragraphs)
                 if self._REFERENCES_HEADING_RE.match(p.text.strip())),
                None,
            )
            if heading_idx is None or heading_idx == first_ref_idx - 1:
                return  # заголовка нет, либо он уже стоит на своём месте

            heading_p = paragraphs[heading_idx]
            target_p = paragraphs[first_ref_idx]
            heading_elem = heading_p._p
            heading_elem.getparent().remove(heading_elem)
            target_p._p.addprevious(heading_elem)

            doc.save(docx_path)
            self.warnings.append(
                "Заголовок списка литературы был смещён относительно "
                "самого списка (см. расположение полей в DOCX-шаблоне) "
                "и автоматически перенесён на место перед списком."
            )
        except Exception as e:
            self.warnings.append(
                f"Не удалось скорректировать положение заголовка списка литературы: {e}"
            )

    def _apply_post_formatting(self, docx_path: str):
        try:
            doc = docx.Document(docx_path)

            for p in doc.paragraphs:
                text_str = p.text.strip()
                if re.match(r"^(?:Рис\.|Рисунок|Figure|Fig\.)\s*\d+", text_str, re.IGNORECASE):
                    p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER

            for tbl in doc.tables:
                self._enforce_table_font(tbl)
                tbl.alignment = docx.enum.table.WD_TABLE_ALIGNMENT.CENTER
                tblPr = tbl._tbl.tblPr
                old_borders = tblPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblBorders")
                if old_borders is not None:
                    tblPr.remove(old_borders)
                borders = parse_xml(r'''
                    <w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                        <w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>
                        <w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>
                        <w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>
                        <w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>
                        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>
                        <w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>
                    </w:tblBorders>
                ''')
                tblPr.append(borders)

            doc.save(docx_path)
        except Exception as e:
            self.warnings.append(f"Ошибка пост-обработки вёрстки: {e}")

    def format_material(
            self,
            metadata: Dict[str, Any],
            output_docx_path: str,
            output_report_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Выполняет полный этап workflow "format_to_template" (ТЗ п.10, 21).

        Возвращает formatting_report.json (контракт ТЗ п.21.4).
        """
        self.filled_fields.clear()
        self.missing_fields.clear()
        self.warnings.clear()

        if not self.engine.load_template():
            return {
                "status": "failed",
                "template_used": os.path.basename(self.template_path),
                "filled_fields": [],
                "missing_fields": [],
                "warnings": self.engine.warnings.copy(),
                "output_docx": "",
            }

        context = self._build_context(metadata)
        if not self.engine.render(context) or not self.engine.save(
                output_docx_path
        ):
            return {
                "status": "failed",
                "template_used": os.path.basename(self.template_path),
                "filled_fields": self.filled_fields.copy(),
                "missing_fields": self.missing_fields.copy(),
                "warnings": self.warnings + self.engine.warnings,
                "output_docx": "",
            }

        self._restore_paragraphs_and_breaks(output_docx_path)
        self._transfer_tables(output_docx_path, metadata)
        self._transfer_figures(output_docx_path, metadata)
        self._transfer_equations(output_docx_path, metadata)
        self._fix_references_heading_position(output_docx_path)
        self._apply_post_formatting(output_docx_path)

        status = (
            "success"
            if not self.missing_fields and not self.warnings
            else "partial"
        )
        report = {
            "status": status,
            "template_used": os.path.basename(self.template_path),
            "filled_fields": self.filled_fields.copy(),
            "missing_fields": self.missing_fields.copy(),
            "warnings": self._dedup_warnings(
                self.warnings
                + self.engine.warnings
                + metadata.get("warnings", [])
            ),
            "output_docx": output_docx_path,
        }

        if output_report_path is not None:
            try:
                report_dir = os.path.dirname(output_report_path)
                if report_dir:
                    os.makedirs(report_dir, exist_ok=True)
                with open(output_report_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
            except Exception as e:
                report["warnings"].append(f"Не удалось сохранить отчёт: {e}")
        return report

    def _dedup_warnings(self, warnings: List[str]) -> List[str]:
        return list(dict.fromkeys(warnings))


def format_to_template(
        extracted_metadata: Union[Dict[str, Any], str],
        template_path: str,
        output_docx_path: str,
        output_report_path: Optional[str] = None,
        original_docx_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ЕДИНСТВЕННАЯ рекомендуемая точка входа модуля для остальных
    разработчиков проекта (workflow-этап "format_to_template", ТЗ п.10, 21).

    Parameters
    ----------
    extracted_metadata : dict | str
        Либо готовый словарь — результат
        docx_processing.metadata_parser.extract_metadata() (контракт
        ТЗ п.20.3), либо путь к сохранённому на диске
        extracted_metadata.json — в этом случае функция сама его прочитает.
    template_path : str
        Путь к DOCX-шаблону конференции (ТЗ п.21.3).
    output_docx_path : str
        Куда сохранить formatted_material.docx (ТЗ п.8.1, files.formatted_docx).
    output_report_path : str, optional
        Куда сохранить formatting_report.json (ТЗ п.21.4). Если не указан,
        отчёт только возвращается функцией, но не пишется на диск.
    original_docx_path : str, optional
        Путь к исходному original.docx — используется только для более
        надёжного поиска файлов изображений на диске.

    Returns
    -------
    dict — formatting_report.json (контракт ТЗ п.21.4). Функция никогда
    не бросает исключения наружу.
    """
    if isinstance(extracted_metadata, str):
        metadata = MaterialFormatter.load_extracted_metadata(extracted_metadata)
        if not metadata:
            return {
                "status": "failed",
                "template_used": os.path.basename(template_path),
                "filled_fields": [],
                "missing_fields": [],
                "warnings": [f"Не удалось загрузить extracted_metadata.json: {extracted_metadata}"],
                "output_docx": "",
            }
    else:
        metadata = extracted_metadata

    formatter = MaterialFormatter(template_path, original_docx_path)
    return formatter.format_material(metadata, output_docx_path, output_report_path)