from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable

from .toc_builder import group_by_section

_HEAD = """<!doctype html>
<html lang="ru" class="scroll-smooth">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">

<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {{
    theme: {{
      extend: {{
        fontFamily: {{
          sans: ['Instrument Sans', 'system-ui', 'sans-serif'],
          serif: ['Instrument Serif', 'Georgia', 'serif'],
        }},
        colors: {{
          primary: '#8b5cf6',
          'primary-dark': '#7c3aed',
          'primary-light': '#a78bfa',
          accent: '#ec4899',
        }},
        borderRadius: {{ '4xl': '2rem', '5xl': '2.5rem' }},
      }}
    }}
  }}
</script>

<style>
  body {{ font-family: 'Instrument Sans', system-ui, sans-serif; background: #000000; color: rgba(255,255,255,0.8); min-height: 100vh; }}
  .glass {{ background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%); backdrop-filter: blur(20px) saturate(180%); -webkit-backdrop-filter: blur(20px) saturate(180%); box-shadow: 0 8px 32px 0 rgba(31,38,135,0.15), inset 0 1px 0 0 rgba(255,255,255,0.2), inset 0 -1px 0 0 rgba(255,255,255,0.1); }}
  .glass-strong {{ background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.08) 100%); backdrop-filter: blur(30px) saturate(200%); -webkit-backdrop-filter: blur(30px) saturate(200%); box-shadow: 0 8px 32px 0 rgba(31,38,135,0.2), inset 0 2px 0 0 rgba(255,255,255,0.25), inset 0 -2px 0 0 rgba(255,255,255,0.15); }}
  a.material-link {{ color: #a78bfa; text-decoration: none; font-weight: 500; }}
  a.material-link:hover {{ color: #ffffff; text-decoration: underline; }}
</style>
</head>
<body class="min-h-screen">
"""

_FOOT = """
</body>
</html>
"""


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
            title = (submission.get("metadata") or {}).get("title_ru") or submission["submission_id"]
            authors = ", ".join(a.get("full_name", "") for a in submission.get("authors", []) if a.get("full_name"))
            items.append(f"""
        <div class="glass rounded-4xl p-5">
          <a class="material-link" href="{escape(material_link_fn(submission['submission_id']))}">{escape(title)}</a>
          {f'<p class="text-white/50 text-sm mt-1">{escape(authors)}</p>' if authors else ''}
        </div>""")
        section_blocks.append(f"""
    <section class="mb-10">
      <h2 class="text-2xl font-bold italic text-white mb-4">{escape(section["title"])}</h2>
      <div class="space-y-3">{''.join(items)}</div>
    </section>""")

    collection_button = (
        f'<a href="{escape(collection_link)}" '
        f'class="inline-block px-6 py-3 rounded-full bg-primary hover:bg-primary-dark transition-all duration-300 text-white font-semibold">'
        f'Скачать сборник PDF</a>'
        if collection_link else ""
    )

    header = f"""
<div class="max-w-4xl mx-auto px-6 py-10">
  <div class="glass-strong rounded-4xl p-8 md:p-10 mb-10">
    <p class="text-primary-light text-sm mb-2">{escape(conference.get("title") or "Конференция")}</p>
    <h1 class="text-3xl font-bold text-white mb-4">{escape(issue["title"])}</h1>
    <p class="text-white/60 mb-6">{issue["year"]} год &middot; Q{issue["quarter"]} &middot; дата выпуска: {escape(issue.get("published_at") or "—")}</p>
    {collection_button}
  </div>
{"".join(section_blocks)}
</div>"""

    return _HEAD.format(title=escape(issue["title"])) + header + _FOOT


def save_archive_html(html_content: str, output_path: str | Path) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    return str(output_path)