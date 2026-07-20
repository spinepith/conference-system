"""Electronic conference collection builder (title, TOC, sections and materials)."""

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
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .toc_builder import build_toc_entries, count_pdf_pages, group_by_section

PAGE_SIZE = A4
MARGIN = 2.0 * cm


def _font_candidates() -> list[tuple[Path, Path]]:
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    return [
        (windows / "times.ttf", windows / "timesbd.ttf"),
        (windows / "arial.ttf", windows / "arialbd.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf")),
    ]


def _register_fonts() -> tuple[str, str]:
    for regular, bold in _font_candidates():
        if regular.is_file() and bold.is_file():
            try:
                pdfmetrics.registerFont(TTFont("CollectionSerif", str(regular)))
                pdfmetrics.registerFont(TTFont("CollectionSerifBold", str(bold)))
                return "CollectionSerif", "CollectionSerifBold"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = _register_fonts()
STYLES = getSampleStyleSheet()
TITLE = ParagraphStyle("CollectionTitle", parent=STYLES["Title"], fontName=FONT_BOLD, fontSize=20, leading=25, alignment=TA_CENTER)
SUBTITLE = ParagraphStyle("CollectionSubtitle", parent=STYLES["Normal"], fontName=FONT_REGULAR, fontSize=12, leading=17, alignment=TA_CENTER)
H1 = ParagraphStyle("CollectionH1", parent=STYLES["Heading1"], fontName=FONT_BOLD, alignment=TA_CENTER)
H2 = ParagraphStyle("CollectionH2", parent=STYLES["Heading2"], fontName=FONT_BOLD)
BODY = ParagraphStyle("CollectionBody", parent=STYLES["Normal"], fontName=FONT_REGULAR, fontSize=10.5, leading=15)
TOC = ParagraphStyle("CollectionToc", parent=BODY, fontSize=10)
TOC_PAGE = ParagraphStyle("CollectionTocPage", parent=TOC, alignment=TA_RIGHT)


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


def _front_flowables(conference: dict[str, Any], issue: dict[str, Any], toc_sections: list[dict[str, Any]] | None = None) -> list:
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
    if toc_sections is not None:
        flow += [Paragraph("СОДЕРЖАНИЕ", H1), Spacer(1, 0.4 * cm)]
        rows = []
        for section in toc_sections:
            rows.append([Paragraph(escape(section["title"]), H2), Paragraph(str(section["start_page"]), TOC_PAGE)])
            for item in section["submissions"]:
                title = ((item.get("metadata") or {}).get("title_ru") or item.get("submission_id", ""))
                authors = ", ".join(a.get("full_name", "") for a in item.get("authors", []) if a.get("full_name"))
                label = f"{authors}. {title}" if authors else title
                rows.append([Paragraph(escape(label), TOC), Paragraph(str(item["page"]), TOC_PAGE)])
        if rows:
            table = Table(rows, colWidths=[A4[0] - 2 * MARGIN - 1.4 * cm, 1.4 * cm])
            table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            flow.append(table)
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


def _stamp_numbers(writer: PdfWriter, skip: set[int]) -> None:
    for index, page in enumerate(writer.pages):
        if index in skip:
            continue
        width = float(page.mediabox.width)
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, float(page.mediabox.height)))
        c.setFont(FONT_REGULAR, 9)
        x = 1.5 * cm if (index + 1) % 2 == 0 else width - 1.8 * cm
        c.drawString(x, 1.0 * cm, str(index + 1))
        c.save()
        packet.seek(0)
        overlay = PdfReader(packet).pages[0]
        page.merge_page(overlay)


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
            front_without_toc = tmpdir / "front_without_toc.pdf"
            front_pages = _build_pdf(_front_flowables(conference, issue), front_without_toc)
            sections = group_by_section(valid)
            # First TOC pass determines its page count.
            provisional, _ = build_toc_entries(sections, front_pages + 2)
            toc_probe = tmpdir / "toc_probe.pdf"
            toc_pages = _build_pdf([Paragraph("СОДЕРЖАНИЕ", H1)] + [Paragraph(escape(s["title"]), BODY) for s in provisional] + [PageBreak()], toc_probe)
            toc_sections, _ = build_toc_entries(sections, front_pages + toc_pages + 1)
            front_path = tmpdir / "front.pdf"
            _build_pdf(_front_flowables(conference, issue, toc_sections), front_path)

            writer = PdfWriter()
            skip_numbers: set[int] = set()
            for page in PdfReader(str(front_path)).pages:
                skip_numbers.add(len(writer.pages))
                writer.add_page(page)

            included: list[str] = []
            for section in toc_sections:
                divider = tmpdir / f"section_{len(writer.pages)}.pdf"
                _section_pdf(section["title"], divider)
                skip_numbers.add(len(writer.pages))
                writer.add_page(PdfReader(str(divider)).pages[0])
                for submission in section["submissions"]:
                    reader = PdfReader(str((submission.get("files") or {})["formatted_pdf"]))
                    for page in reader.pages:
                        writer.add_page(page)
                    included.append(submission["submission_id"])

            output_data = tmpdir / "output.pdf"
            _output_pdf(conference, issue, output_data)
            for page in PdfReader(str(output_data)).pages:
                writer.add_page(page)

            _stamp_numbers(writer, skip_numbers)
            output_path.unlink(missing_ok=True)
            with output_path.open("wb") as fh:
                writer.write(fh)

        status = "partial" if skipped else "success"
        return CollectionBuildResult(status, str(output_path), len(PdfReader(str(output_path)).pages), included, skipped)
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        return CollectionBuildResult("failed", None, 0, [], skipped, str(exc))
