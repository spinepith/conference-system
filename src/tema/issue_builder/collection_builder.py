from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import Fit
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .toc_builder import build_toc_entries, count_pdf_pages, group_by_section

PAGE_SIZE = A4
MARGIN = 2.0 * cm


def _font_candidates() -> list[tuple[Path, Path, Path]]:
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    return [
        (windows / "times.ttf", windows / "timesbd.ttf", windows / "timesbi.ttf"),
        (windows / "arial.ttf", windows / "arialbd.ttf", windows / "arialbi.ttf"),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-BoldItalic.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf"),
        ),
    ]


def _register_fonts() -> tuple[str, str, str]:
    for regular, bold, bold_italic in _font_candidates():
        if regular.is_file() and bold.is_file() and bold_italic.is_file():
            try:
                pdfmetrics.registerFont(TTFont("CollectionSerif", str(regular)))
                pdfmetrics.registerFont(TTFont("CollectionSerifBold", str(bold)))
                pdfmetrics.registerFont(TTFont("CollectionSerifBoldItalic", str(bold_italic)))
                return "CollectionSerif", "CollectionSerifBold", "CollectionSerifBoldItalic"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", "Helvetica-BoldOblique"


FONT_REGULAR, FONT_BOLD, FONT_BOLD_ITALIC = _register_fonts()
STYLES = getSampleStyleSheet()
TITLE = ParagraphStyle("CollectionTitle", parent=STYLES["Title"], fontName=FONT_BOLD, fontSize=20, leading=25, alignment=TA_CENTER)
SUBTITLE = ParagraphStyle("CollectionSubtitle", parent=STYLES["Normal"], fontName=FONT_REGULAR, fontSize=12, leading=17, alignment=TA_CENTER)
H1 = ParagraphStyle("CollectionH1", parent=STYLES["Heading1"], fontName=FONT_BOLD, alignment=TA_CENTER)
H2 = ParagraphStyle("CollectionH2", parent=STYLES["Heading2"], fontName=FONT_BOLD)
BODY = ParagraphStyle("CollectionBody", parent=STYLES["Normal"], fontName=FONT_REGULAR, fontSize=10.5, leading=15)

# Геометрия страницы содержания (используется и при рисовании, и при
# расчёте точечного лидера/переносов строк).
_TOC_FONT_SIZE = 10.5
_TOC_SECTION_FONT_SIZE = 13
_TOC_LINE_HEIGHT = _TOC_FONT_SIZE * 1.35
_TOC_SECTION_GAP = 0.55 * cm
_TOC_ENTRY_GAP = 0.12 * cm
_TOC_PAGE_NUM_WIDTH = 1.3 * cm
_TOC_CONTENT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN
_TOC_LABEL_WIDTH = _TOC_CONTENT_WIDTH - _TOC_PAGE_NUM_WIDTH


@dataclass
class CollectionBuildResult:
    status: str
    output_path: str | None
    page_count: int
    included_submissions: list[str]
    skipped_submissions: list[dict[str, str]]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output_path": self.output_path,
            "page_count": self.page_count,
            "included_submissions": self.included_submissions,
            "skipped_submissions": self.skipped_submissions,
            "error": self.error,
        }


def _build_pdf(flowables: list, path: Path) -> int:
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN)
    doc.build(flowables)
    return len(PdfReader(str(path)).pages)


def _front_flowables(conference: dict[str, Any], issue: dict[str, Any]) -> list:
    """Титул + информация о конференции + оргкомитет (без содержания —
    оно теперь рисуется отдельно, через _build_toc_pdf, чтобы можно было
    сделать пункты содержания кликабельными)."""
    flow = [
        Spacer(1, 5.2 * cm),
        Paragraph(escape(conference.get("title") or "Материалы конференции"), TITLE),
        Spacer(1, 0.7 * cm),
        Paragraph(escape(issue["title"]), SUBTITLE),
        Spacer(1, 0.35 * cm),
        Paragraph(f"{issue['year']} год, квартал {issue['quarter']}", SUBTITLE),
        Spacer(1, 0.35 * cm),
        Paragraph(f"Дата выпуска: {escape(issue.get('published_at') or date.today().isoformat())}", SUBTITLE),
        PageBreak(),
    ]
    if conference.get("description"):
        flow += [Paragraph("О конференции", H1), Spacer(1, 0.35 * cm), Paragraph(escape(conference["description"]), BODY), PageBreak()]
    committee = issue.get("org_committee") or []
    if committee:
        flow += [Paragraph("Организационный комитет", H1), Spacer(1, 0.35 * cm)]
        flow.extend(Paragraph("• " + escape(str(member)), BODY) for member in committee)
        flow.append(PageBreak())
    return flow


def _section_pdf(title: str, path: Path) -> None:
    _build_pdf([Spacer(1, 9 * cm), Paragraph(escape(title), TITLE)], path)


def _output_pdf(conference: dict[str, Any], issue: dict[str, Any], path: Path) -> None:
    _build_pdf([
        Spacer(1, 4 * cm),
        Paragraph("Выходные данные", H1),
        Spacer(1, 0.5 * cm),
        Paragraph(escape(conference.get("title") or "Материалы конференции"), BODY),
        Paragraph(escape(issue["title"]), BODY),
        Paragraph(f"Год: {issue['year']}. Квартал: {issue['quarter']}.", BODY),
        Paragraph(f"Дата выпуска: {escape(issue.get('published_at') or date.today().isoformat())}.", BODY),
    ], path)


def _entry_label(item: dict[str, Any]) -> str:
    title = (item.get("metadata") or {}).get("title_ru") or item.get("submission_id", "")
    authors = ", ".join(a.get("full_name", "") for a in item.get("authors", []) if a.get("full_name"))
    return f"{authors}. {title}" if authors else title


def _wrap_by_width(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    """Переносит строку по словам так, чтобы каждая строка помещалась в
    max_width (в пунктах) при заданном шрифте — нужно, чтобы вручную
    рисовать текст на canvas с точным контролем положения (для кликабельных
    ссылок в содержании)."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _dot_leader(label_last_line: str, page_str: str, font_name: str, font_size: float, max_width: float) -> str:
    """Достраивает точки между последней строкой названия и номером
    страницы, чтобы визуально получился классический пунктирный лидер
    (как в настоящих сборниках)."""
    label_width = stringWidth(label_last_line, font_name, font_size)
    page_width = stringWidth(page_str, font_name, font_size)
    dot_width = stringWidth(".", font_name, font_size)
    space_width = stringWidth(" ", font_name, font_size)
    gap = max_width - label_width - page_width - 2 * space_width
    if gap < dot_width * 3:
        return label_last_line
    dot_count = int(gap / dot_width)
    return f"{label_last_line} {'.' * dot_count}"


class _TocLinkSpec:
    __slots__ = ("toc_page_index", "x0", "y0", "x1", "y1", "target_page")

    def __init__(self, toc_page_index: int, x0: float, y0: float, x1: float, y1: float, target_page: int):
        self.toc_page_index = toc_page_index
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.target_page = target_page


def _build_toc_pdf(toc_sections: list[dict[str, Any]], path: Path) -> tuple[int, list[_TocLinkSpec]]:
    """Рисует страницу(ы) "СОДЕРЖАНИЕ" вручную на canvas (а не через
    Platypus-таблицу) — это даёт точные координаты каждой строки, поверх
    которых чуть позже накладываются кликабельные ссылки (см.
    build_collection_pdf: writer.add_annotation с Link).
    """
    width, height = PAGE_SIZE
    top_y = height - MARGIN
    bottom_y = MARGIN

    c = canvas.Canvas(str(path), pagesize=PAGE_SIZE)
    links: list[_TocLinkSpec] = []
    page_index = 0
    y = top_y

    def new_page() -> None:
        nonlocal y, page_index
        c.showPage()
        page_index += 1
        y = top_y

    c.setFont(FONT_BOLD, 18)
    c.drawCentredString(width / 2, y - 18, "СОДЕРЖАНИЕ")
    y -= 18 + 1.0 * cm

    for section in toc_sections:
        needed = _TOC_SECTION_GAP + _TOC_LINE_HEIGHT
        if y - needed < bottom_y:
            new_page()
        c.setFont(FONT_BOLD_ITALIC, _TOC_SECTION_FONT_SIZE)
        c.drawString(MARGIN, y, section["title"])
        y -= _TOC_LINE_HEIGHT + _TOC_ENTRY_GAP

        for item in section["submissions"]:
            label = _entry_label(item)
            page_str = str(item["page"])
            lines = _wrap_by_width(label, FONT_REGULAR, _TOC_FONT_SIZE, _TOC_LABEL_WIDTH)

            if y - _TOC_LINE_HEIGHT * len(lines) < bottom_y:
                new_page()

            entry_top_y = y
            for i, line in enumerate(lines):
                is_last = i == len(lines) - 1
                text = _dot_leader(line, page_str, FONT_REGULAR, _TOC_FONT_SIZE, _TOC_LABEL_WIDTH) if is_last else line
                c.setFont(FONT_REGULAR, _TOC_FONT_SIZE)
                c.drawString(MARGIN, y, text)
                if is_last:
                    c.drawRightString(MARGIN + _TOC_CONTENT_WIDTH, y, page_str)
                y -= _TOC_LINE_HEIGHT
            entry_bottom_y = y + (_TOC_LINE_HEIGHT - 0.2 * cm)
            links.append(_TocLinkSpec(page_index, MARGIN, entry_bottom_y, MARGIN + _TOC_CONTENT_WIDTH, entry_top_y + 0.2 * cm, item["page"]))
            y -= _TOC_ENTRY_GAP

        y -= _TOC_SECTION_GAP - _TOC_ENTRY_GAP

    c.showPage()
    c.save()
    return page_index + 1, links


def _stamp_numbers(writer: PdfWriter, header_text: str, skip: set[int]) -> None:
    """Нумерация страниц + бегущий колонтитул с названием сборника и
    линия-разделитель под ним (чётные страницы — номер слева, нечётные —
    справа)."""
    for index, page in enumerate(writer.pages):
        if index in skip:
            continue
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))

        header_y = height - 1.1 * cm
        c.setFont(FONT_BOLD, 9)
        c.drawCentredString(width / 2, header_y, header_text)
        c.setLineWidth(0.6)
        c.line(MARGIN, header_y - 0.25 * cm, width - MARGIN, header_y - 0.25 * cm)

        page_number = index + 1
        c.setFont(FONT_REGULAR, 9)
        if page_number % 2 == 0:
            c.drawString(MARGIN, 1.0 * cm, str(page_number))
        else:
            c.drawRightString(width - MARGIN, 1.0 * cm, str(page_number))

        c.save()
        packet.seek(0)
        overlay = PdfReader(packet).pages[0]
        page.merge_page(overlay)


def _issue_header_text(conference: dict[str, Any], issue: dict[str, Any]) -> str:
    return conference.get("title") or issue.get("title") or ""


def build_collection_pdf(
    conference: dict[str, Any],
    issue: dict[str, Any],
    submissions: list[dict[str, Any]],
    output_path: str | Path,
) -> CollectionBuildResult:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    valid: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for submission in submissions:
        pdf_path = (submission.get("files") or {}).get("formatted_pdf")
        try:
            if not pdf_path or count_pdf_pages(submission) <= 0:
                raise ValueError("formatted_material.pdf отсутствует или повреждён")
            valid.append(submission)
        except Exception as exc:
            skipped.append({"submission_id": submission.get("submission_id", ""), "reason": str(exc)})

    if not valid:
        return CollectionBuildResult("failed", None, 0, [], skipped, "Нет ни одного корректного PDF материала.")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)

            front_path = tmpdir / "front.pdf"
            front_pages = _build_pdf(_front_flowables(conference, issue), front_path)
            sections = group_by_section(valid)

            # Два прохода: сначала черновой расчёт номеров страниц (чтобы
            # узнать, сколько страниц займёт само содержание), потом —
            # финальный, с уже точными номерами.
            provisional_sections, _ = build_toc_entries(sections, front_pages + 1)
            toc_probe_path = tmpdir / "toc_probe.pdf"
            toc_pages, _ = _build_toc_pdf(provisional_sections, toc_probe_path)

            material_start_page = front_pages + toc_pages + 1
            toc_sections, _ = build_toc_entries(sections, material_start_page)
            toc_final_path = tmpdir / "toc_final.pdf"
            _, toc_links = _build_toc_pdf(toc_sections, toc_final_path)

            writer = PdfWriter()
            skip_numbers: set[int] = set()

            for page in PdfReader(str(front_path)).pages:
                skip_numbers.add(len(writer.pages))
                writer.add_page(page)

            toc_page_offset = len(writer.pages)
            for page in PdfReader(str(toc_final_path)).pages:
                writer.add_page(page)

            included: list[str] = []
            for section in toc_sections:
                divider = tmpdir / f"section_{len(writer.pages)}.pdf"
                _section_pdf(section["title"], divider)
                section_page_index = len(writer.pages)
                skip_numbers.add(section_page_index)
                writer.add_page(PdfReader(str(divider)).pages[0])

                section_outline = writer.add_outline_item(section["title"], section_page_index)
                for submission in section["submissions"]:
                    material_page_index = len(writer.pages)
                    reader = PdfReader(str((submission.get("files") or {})["formatted_pdf"]))
                    for page in reader.pages:
                        writer.add_page(page)
                    included.append(submission["submission_id"])
                    writer.add_outline_item(_entry_label(submission)[:120], material_page_index, parent=section_outline)

            output_data = tmpdir / "output.pdf"
            _output_pdf(conference, issue, output_data)
            for page in PdfReader(str(output_data)).pages:
                writer.add_page(page)

            header_text = _issue_header_text(conference, issue)
            _stamp_numbers(writer, header_text, skip_numbers)

            for link in toc_links:
                absolute_toc_page = toc_page_offset + link.toc_page_index
                writer.add_annotation(
                    page_number=absolute_toc_page,
                    annotation=Link(
                        rect=(link.x0, link.y0, link.x1, link.y1),
                        target_page_index=link.target_page - 1,
                        fit=Fit.fit(),
                    ),
                )

            output_path.unlink(missing_ok=True)
            with output_path.open("wb") as fh:
                writer.write(fh)

        status = "partial" if skipped else "success"
        return CollectionBuildResult(status, str(output_path), len(PdfReader(str(output_path)).pages), included, skipped)
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        return CollectionBuildResult("failed", None, 0, [], skipped, str(exc))