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
    for section_index, section in enumerate(group_by_section(submissions), start=1):
        items = []
        for submission in section["submissions"]:
            title = ((submission.get("metadata") or {}).get("title_ru") or submission["submission_id"])
            authors = ", ".join(
                author.get("full_name", "")
                for author in submission.get("authors", [])
                if author.get("full_name")
            )
            if not authors:
                authors = ((submission.get("author_contact") or {}).get("full_name") or "Автор не указан")
            submission_id = submission["submission_id"]
            items.append(
                '<article class="material">'
                f'<div class="material__number">{escape(str(submission_id))}</div>'
                f'<h3>{escape(title)}</h3>'
                f'<p>{escape(authors)}</p>'
                f'<a href="{escape(material_link_fn(submission_id))}">Открыть PDF <span>→</span></a>'
                '</article>'
            )
        section_blocks.append(
            '<section class="archive-section">'
            f'<div class="section-heading"><span>{section_index:02d}</span><h2>{escape(section["title"])}</h2>'
            f'<small>{len(items)} материалов</small></div>'
            f'<div class="material-grid">{"".join(items)}</div>'
            '</section>'
        )

    collection = (
        f'<a class="button" href="{escape(collection_link)}">Скачать сборник PDF</a>'
        if collection_link
        else ""
    )
    conference_title = escape(conference.get("title") or "Научная конференция")
    issue_title = escape(issue["title"])
    published_at = escape(issue.get("published_at") or "—")

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Электронный выпуск научной конференции">
<title>{issue_title}</title>
<style>
:root{{--navy:#08152f;--navy2:#183266;--blue:#2457d6;--soft:#f3f6fb;--line:#e2e8f0;--text:#111827;--muted:#64748b;--white:#fff}}
*{{box-sizing:border-box}}html{{height:100%;min-height:100%;scroll-behavior:smooth}}body{{display:flex;min-height:100vh;min-height:100dvh;margin:0;flex-direction:column;color:var(--text);background:var(--soft);font:16px/1.55 Inter,"Segoe UI",Arial,sans-serif}}a{{color:var(--blue);text-decoration:none}}.shell{{width:min(1160px,calc(100% - 40px));margin:0 auto}}.topbar{{background:var(--white);border-bottom:1px solid var(--line)}}.topbar__inner{{min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:20px}}.brand{{display:flex;align-items:center;gap:11px;color:var(--navy);font-weight:800}}.brand__mark{{display:grid;width:40px;height:40px;place-items:center;color:white;background:linear-gradient(145deg,var(--blue),#5b8cf6);border-radius:12px}}.brand small{{display:block;color:var(--muted);font-size:11px;font-weight:600}}.hero{{padding:76px 0;color:white;background:linear-gradient(120deg,var(--navy),var(--navy2))}}.hero__content{{display:grid;grid-template-columns:1fr auto;align-items:end;gap:30px}}.eyebrow{{display:inline-block;margin-bottom:15px;color:#9bb8ff;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}}h1{{max-width:850px;margin:0 0 18px;font-size:clamp(36px,5vw,64px);line-height:1.06;letter-spacing:-.04em}}.hero p{{margin:0;color:#c6d2e7}}.hero__meta{{display:flex;flex-wrap:wrap;gap:12px 22px;margin-top:24px;font-size:13px}}.button{{display:inline-flex;min-height:48px;align-items:center;padding:12px 20px;color:var(--blue);background:white;border-radius:12px;font-weight:800;white-space:nowrap}}main{{flex:1 0 auto;padding:65px 0}}.archive-section{{margin-bottom:58px}}.section-heading{{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:16px;margin-bottom:24px}}.section-heading>span{{display:grid;width:42px;height:42px;place-items:center;color:var(--blue);background:#e9f0ff;border-radius:12px;font-size:12px;font-weight:800}}.section-heading h2{{margin:0;color:var(--navy);font-size:clamp(24px,3vw,34px);letter-spacing:-.03em}}.section-heading small{{color:var(--muted)}}.material-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px}}.material{{padding:24px;background:white;border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 25px rgba(20,39,80,.06)}}.material__number{{margin-bottom:13px;color:var(--muted);font:12px "SFMono-Regular",Consolas,monospace}}.material h3{{margin:0 0 10px;color:var(--navy);font-size:18px;line-height:1.3}}.material p{{margin:0 0 18px;color:var(--muted);font-size:14px}}.material a{{display:inline-flex;gap:6px;font-size:14px;font-weight:800}}.material a span{{transition:transform .2s}}.material a:hover span{{transform:translateX(3px)}}.empty{{padding:40px;background:white;border:1px dashed #cbd5e1;border-radius:16px;text-align:center;color:var(--muted)}}footer{{padding:30px 0;color:#8f9db5;background:var(--navy);font-size:13px}}footer .shell{{display:flex;justify-content:space-between;gap:20px}}@media(max-width:760px){{.shell{{width:min(100% - 24px,1160px)}}.hero{{padding:55px 0}}.hero__content{{grid-template-columns:1fr}}.material-grid{{grid-template-columns:1fr}}.section-heading{{grid-template-columns:auto 1fr}}.section-heading small{{grid-column:2}}footer .shell{{flex-direction:column}}}}
</style>
</head>
<body>
<header class="topbar"><div class="shell topbar__inner"><div class="brand"><span class="brand__mark">AI</span><span>{conference_title}<small>электронный архив</small></span></div><span>Научные материалы</span></div></header>
<section class="hero"><div class="shell hero__content"><div><span class="eyebrow">Опубликованный выпуск</span><h1>{issue_title}</h1><p>Электронный сборник материалов конференции</p><div class="hero__meta"><span>{issue["year"]} год</span><span>Q{issue["quarter"]}</span><span>Дата выпуска: {published_at}</span><span>Материалов: {len(submissions)}</span></div></div>{collection}</div></section>
<main><div class="shell">{"".join(section_blocks) if section_blocks else '<div class="empty">В выпуске пока нет материалов.</div>'}</div></main>
<footer><div class="shell"><span>{conference_title}</span><span>Автоматизированная система управления конференцией</span></div></footer>
</body>
</html>"""


def ensure_archive_sticky_footer(html_content: str) -> str:
    """Upgrade previously generated archive pages to the current flex layout."""
    html_content = html_content.replace(
        'html{scroll-behavior:smooth}body{margin:0',
        'html{height:100%;min-height:100%;scroll-behavior:smooth}'
        'body{display:flex;min-height:100vh;min-height:100dvh;margin:0;flex-direction:column',
    )
    html_content = html_content.replace(
        'main{padding:65px 0}',
        'main{flex:1 0 auto;padding:65px 0}',
    )
    return html_content


def save_archive_html(html_content: str, output_path: str | Path) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    return str(output_path)
