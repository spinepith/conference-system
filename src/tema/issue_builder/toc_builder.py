from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pypdf import PdfReader


def count_pdf_pages(submission: dict[str, Any]) -> int:
    path_value = (submission.get("files") or {}).get("formatted_pdf")
    if not path_value:
        return 0
    try:
        return len(PdfReader(str(Path(path_value))).pages)
    except Exception:
        return 0


def group_by_section(submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for submission in submissions:
        section = ((submission.get("metadata") or {}).get("section") or "Без секции").strip()
        grouped.setdefault(section, []).append(submission)

    def section_key(title: str):
        return (title == "Без секции", title.casefold())

    result: list[dict[str, Any]] = []
    for title in sorted(grouped, key=section_key):
        rows = sorted(
            grouped[title],
            key=lambda row: (
                ((row.get("metadata") or {}).get("title_ru") or "").casefold(),
                row.get("submission_id", ""),
            ),
        )
        result.append({"title": title, "submissions": rows})
    return result


def build_toc_entries(
    sections: list[dict[str, Any]],
    start_page: int,
    page_count_fn: Callable[[dict[str, Any]], int] = count_pdf_pages,
) -> tuple[list[dict[str, Any]], int]:
    page = start_page
    result: list[dict[str, Any]] = []
    for section in sections:
        section_page = page
        page += 1
        entries = []
        for submission in section["submissions"]:
            pages = page_count_fn(submission) or 1
            entries.append({**submission, "page": page, "page_count": pages})
            page += pages
        result.append({"title": section["title"], "start_page": section_page, "submissions": entries})
    return result, page
