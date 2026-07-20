from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable

from .toc_builder import group_by_section


def build_archive_html(
    conference: dict[str, Any],
    issue: dict[str, Any],
    submissions: list[dict[str, Any]],
    material_link_fn: Callable[[str], str],
    collection_link: str | None,
) -> str:
    section_blocks = []
    for section in group_by_section(submissions):
        items = []
        for submission in section["submissions"]:
            title = ((submission.get("metadata") or {}).get("title_ru") or submission["submission_id"])
            authors = ", ".join(a.get("full_name", "") for a in submission.get("authors", []) if a.get("full_name"))
            items.append(
                f'<li><a href="{escape(material_link_fn(submission["submission_id"]))}">{escape(title)}</a>'
                f'<div class="authors">{escape(authors)}</div></li>'
            )
        section_blocks.append(f'<section><h2>{escape(section["title"])}</h2><ul>{"".join(items)}</ul></section>')
    collection = f'<a class="button" href="{escape(collection_link)}">Скачать сборник PDF</a>' if collection_link else ""
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(issue["title"])}</title>
<style>body{{font-family:Arial,sans-serif;max-width:960px;margin:40px auto;padding:0 20px;color:#1f2937}}header{{padding:30px;background:#f3f4f6;border-radius:16px}}section{{margin:30px 0}}li{{margin:14px 0}}.authors{{color:#6b7280;margin-top:4px}}.button{{display:inline-block;padding:11px 16px;background:#2563eb;color:white;border-radius:9px;text-decoration:none}}</style>
</head><body><header><p>{escape(conference.get("title") or "Конференция")}</p><h1>{escape(issue["title"])}</h1>
<p>{issue["year"]} год · Q{issue["quarter"]} · дата выпуска: {escape(issue.get("published_at") or "—")}</p>{collection}</header>
{"".join(section_blocks)}</body></html>"""


def save_archive_html(html_content: str, output_path: str | Path) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    return str(output_path)
