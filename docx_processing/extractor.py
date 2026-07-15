"""
Внутренний низкоуровневый модуль. ТЗ, раздел 20 "DOCX-извлечение и анализ
структуры материала".

ВНИМАНИЕ ДЛЯ ДРУГИХ РАЗРАБОТЧИКОВ ПРОЕКТА:
Класс DocxExtractor — деталь реализации. Снаружи модуля docx_processing
его использовать не нужно. Единственная точка входа для интеграции —
docx_processing.service.extract_metadata(...) (см. service.py и README.md
в корне модуля). Там же описан итоговый JSON-контракт (ТЗ, п. 20.3).

Этот файл отвечает только за физическое чтение DOCX (python-docx + lxml):
- сохраняет порядок абзацев/таблиц как в исходном файле;
- выносит формулы (oMath/OLE) и изображения в отдельные объекты,
  оставляя в тексте служебные токены [[EQUATION_N]] / [[IMAGE_N]] —
  эти же токены затем понимает docx_processing.formatter при переносе
  объектов в оформленный документ.
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree


class DocxExtractor:
    """Низкоуровневый извлекатель текста, таблиц, формул и изображений из DOCX-файла
    с сохранением физического порядка и изоляцией математических объектов.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.doc: docx.Document | None = None
        self.warnings: List[str] = []
        self.equation_counter = 0
        self.image_counter = 0
        self.extracted_equations: Dict[str, str] = {}
        self.saved_images_list: List[Dict[str, Any]] = []

    def load_document(self) -> bool:
        if not os.path.exists(self.file_path):
            self.warnings.append(f"Файл не найден: {self.file_path}")
            return False
        try:
            self.doc = docx.Document(self.file_path)
            return True
        except Exception as e:
            self.warnings.append(
                f"Ошибка чтения DOCX файла '{self.file_path}': {str(e)}"
            )
            return False

    def _elem_to_str(self, elem) -> str:
        try:
            if hasattr(elem, "xml"):
                return elem.xml.lower()
            return etree.tostring(elem, encoding="unicode").lower()
        except Exception:
            return str(elem).lower()

    def _is_math_ole(self, ole_elem) -> bool:
        progids = ole_elem.xpath(
            './/@*[local-name()="progid" or local-name()="ProgID"] '
            '| ./@*[local-name()="progid" or local-name()="ProgID"]'
        )
        for progid in progids:
            if any(k in str(progid).lower() for k in ["equation", "mathtype", "mtef", "oleobject"]):
                return True
        return False

    def _has_math(self, element) -> bool:
        if element is None:
            return False
        if len(element.xpath('.//*[local-name()="oMath"]')) > 0:
            return True
        for ole in element.xpath(
                './/*[local-name()="OLEObject"] | .//*[local-name()="object"]'
        ):
            if self._is_math_ole(ole):
                return True
        return False

    def _is_inside_math(self, elem) -> bool:
        for ancestor in elem.xpath("ancestor-or-self::*"):
            tag = ancestor.tag.split("}")[-1]
            if tag in ("oMath", "oMathPara"):
                return True
            if self._is_math_ole(ancestor):
                return True
        return False

    def _extract_emu_dims(self, elem) -> Tuple[Optional[int], Optional[int]]:
        try:
            extents = elem.xpath(
                "ancestor::*[local-name()='inline' or local-name()='anchor' or local-name()='drawing'][1]//*[local-name()='extent']")
            if extents:
                cx = int(extents[0].get("cx", 0))
                cy = int(extents[0].get("cy", 0))
                if cx > 0 and cy > 0:
                    return cx, cy
        except Exception:
            pass
        return None, None

    def _get_image_rels(self, element) -> List[Dict[str, Any]]:
        r_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
        results = []
        seen_rids = set()

        for blip in element.xpath('.//*[local-name()="blip"]'):
            if self._is_inside_math(blip):
                continue
            rid = blip.get(f"{r_ns}embed") or blip.get(f"{r_ns}link")
            if rid and rid not in seen_rids:
                seen_rids.add(rid)
                cx, cy = self._extract_emu_dims(blip)
                results.append({"rid": rid, "width_emu": cx, "height_emu": cy})

        for img in element.xpath('.//*[local-name()="imagedata"]'):
            if self._is_inside_math(img):
                continue
            rid = img.get(f"{r_ns}id")
            if rid and rid not in seen_rids:
                seen_rids.add(rid)
                cx, cy = self._extract_emu_dims(img)
                results.append({"rid": rid, "width_emu": cx, "height_emu": cy})

        return results

    def _save_single_image(self, img_meta: Dict[str, Any], submission_id: str) -> Optional[str]:
        rid = img_meta["rid"]
        width_emu = img_meta.get("width_emu")
        height_emu = img_meta.get("height_emu")
        try:
            part = self.doc.part.related_parts[rid]
            ext = part.content_type.split("/")[-1]
            if ext == "jpeg":
                ext = "jpg"
            elif ext in ("x-emf", "x-wmf", "emf", "wmf"):
                ext = "emf" if "emf" in ext else "wmf"

            self.image_counter += 1
            file_name = f"{submission_id}_image_{self.image_counter}.{ext}"
            storage_dir = f"storage/submissions/{submission_id}/images"
            os.makedirs(storage_dir, exist_ok=True)
            file_path = os.path.join(storage_dir, file_name)

            with open(file_path, "wb") as f:
                f.write(part.blob)

            if ext in ("emf", "wmf"):
                try:
                    from PIL import Image
                    img = Image.open(file_path)
                    png_name = f"{submission_id}_image_{self.image_counter}.png"
                    png_path = os.path.join(storage_dir, png_name)
                    img.save(png_path, "PNG")
                    file_name, file_path = png_name, png_path
                except Exception as conv_e:
                    self.warnings.append(
                        f"Векторный файл {file_name} требует конвертации в PNG (Pillow: {conv_e})."
                    )

            self.saved_images_list.append({
                "file_name": file_name,
                "file_path": file_path.replace("\\", "/"),
                "content_type": part.content_type,
                "width_emu": width_emu,
                "height_emu": height_emu,
            })
            return f"[[IMAGE_{self.image_counter}]]"
        except Exception as e:
            self.warnings.append(f"Не удалось извлечь изображение rId={rid}: {e}")
            return None

    def _tokenized_paragraph_text(self, p_elem) -> str:
        text_parts = []
        for child in p_elem.iterchildren():
            tag = child.tag.split("}")[-1]
            if tag in ("oMath", "oMathPara") or self._has_math(child):
                self.equation_counter += 1
                token = f"[[EQUATION_{self.equation_counter}]]"
                self.extracted_equations[token] = etree.tostring(
                    child, encoding="unicode"
                )
                text_parts.append(f" {token} ")
            elif tag == "r":
                t_elems = child.xpath('.//*[local-name()="t"]/text()')
                if t_elems:
                    text_parts.append("".join(t_elems))
            else:
                for node in child.xpath('.//*[local-name()="t" or local-name()="br" or local-name()="cr"]'):
                    node_tag = node.tag.split("}")[-1]
                    if node_tag in ("br", "cr"):
                        text_parts.append("\n")
                    elif node.text:
                        text_parts.append(node.text)

        result_text = "".join(text_parts).strip()
        return (
            result_text
            if result_text
            else (p_elem.text.strip() if p_elem.text else "")
        )

    def _iter_block_items(self):
        if not self.doc:
            return
        yield from self._iter_children(self.doc._element.body)

    def _iter_children(self, parent):
        for child in parent.iterchildren():
            tag = child.tag.split("}")[-1]
            if tag == "p":
                yield Paragraph(child, self.doc)
            elif tag == "tbl":
                yield Table(child, self.doc)
            elif tag == "sdt":
                sdt_content = child.find(".//{*}sdtContent")
                if sdt_content is not None:
                    yield from self._iter_children(sdt_content)

    def _extract_table_text(self, table: Table) -> str:
        rows_text = [
            " | ".join([
                cell.text.strip().replace("\n", " ") for cell in row.cells
            ])
            for row in table.rows
        ]
        return "\n".join(rows_text)

    def extract_tables_structured(self) -> List[Dict[str, Any]]:
        if not self.doc and not self.load_document():
            return []
        tables_data, table_index = [], 0
        blocks = list(self._iter_block_items())
        used_caption_indices: set = set()
        for i, block in enumerate(blocks):
            if not isinstance(block, Table):
                continue
            table_index += 1
            rows = [
                [cell.text.strip().replace("\n", " ") for cell in row.cells]
                for row in block.rows
            ]
            caption = ""
            if (
                    i - 1 >= 0
                    and (i - 1) not in used_caption_indices
                    and isinstance(blocks[i - 1], Paragraph)
            ):
                if re.match(
                        r"^(?:Таблица|Table)\s+\d+",
                        blocks[i - 1].text.strip(),
                        re.IGNORECASE,
                ):
                    caption = blocks[i - 1].text.strip()
                    used_caption_indices.add(i - 1)
            tables_data.append({
                "index": table_index,
                "caption": caption,
                "rows_count": len(rows),
                "cols_count": len(rows[0]) if rows else 0,
                "rows": rows,
                "xml": etree.tostring(block._element, encoding="unicode"),
            })
        return tables_data

    def extract_raw_data(self, submission_id: str = "temp_sub") -> Dict[str, Any]:
        """
        Возвращает "сырые" данные документа для MetadataParser.

        Это НЕ формат контракта extracted_metadata.json (ТЗ п.20.3) — это
        промежуточный внутренний формат. Публичный контракт формирует
        MetadataParser.parse() / docx_processing.service.extract_metadata().
        """
        if not self.load_document():
            return {
                "ordered_blocks": [],
                "tables_count": 0,
                "figures_count": 0,
                "equations_count": 0,
                "saved_images": [],
                "structured_tables": [],
                "extracted_equations": {},
                "warnings": self.warnings,
            }

        self.equation_counter = 0
        self.image_counter = 0
        self.extracted_equations.clear()
        self.saved_images_list.clear()
        structured_tables = self.extract_tables_structured()

        ordered_blocks, table_counter = [], 0
        for block in self._iter_block_items():
            if isinstance(block, Paragraph):
                imgs_meta = self._get_image_rels(block._element)
                for img_meta in imgs_meta:
                    img_token = self._save_single_image(img_meta, submission_id)
                    if img_token:
                        ordered_blocks.append({"type": "paragraph", "text": img_token})

                text = self._tokenized_paragraph_text(block._element)
                if text and not re.match(r"^\[\[IMAGE_\d+\]\]$", text.strip()):
                    ordered_blocks.append({"type": "paragraph", "text": text})

            elif isinstance(block, Table):
                table_counter += 1
                ordered_blocks.append({
                    "type": "table",
                    "text": (
                        f"[[TABLE_{table_counter}]]\n[Таблица"
                        f" {table_counter}]\n{self._extract_table_text(block)}"
                    ),
                })

        return {
            "ordered_blocks": ordered_blocks,
            "tables_count": table_counter,
            "figures_count": len(self.saved_images_list),
            "equations_count": len(self.extracted_equations),
            "saved_images": self.saved_images_list,
            "structured_tables": structured_tables,
            "extracted_equations": self.extracted_equations,
            "warnings": self.warnings,
        }