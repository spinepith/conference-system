"""Manual smoke test for the independent DOCX-processing module.

Usage from the repository root::

    python -m src.docx_processing.test_extractor path/to/article.docx

Or with ``src`` added to ``PYTHONPATH``::

    python src/docx_processing/test_extractor.py path/to/article.docx
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow direct execution without installing the package.
MODULE_DIR = Path(__file__).resolve().parent
SRC_ROOT = MODULE_DIR.parent
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from docx_processing.service import extract_metadata, format_to_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the DOCX module smoke test.")
    parser.add_argument("input_docx", type=Path, help="Source DOCX article.")
    parser.add_argument(
        "--template",
        type=Path,
        default=PROJECT_ROOT / "storage" / "templates" / "conference_template_v1.docx",
        help="Conference template path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "storage" / "docx_processing_test",
        help="Directory for generated files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_docx.resolve()
    template_path = args.template.resolve()
    output_dir = args.output_dir.resolve()

    if not input_path.exists():
        print(f"[ERROR] Source DOCX not found: {input_path}", file=sys.stderr)
        return 1
    if not template_path.exists():
        print(f"[ERROR] Template not found: {template_path}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "extracted_metadata.json"
    formatted_path = output_dir / "formatted_material.docx"
    report_path = output_dir / "formatting_report.json"

    metadata = extract_metadata(
        str(input_path),
        submission_id="manual-test",
        storage_dir=str(output_dir),
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = format_to_template(
        metadata,
        str(template_path),
        str(formatted_path),
        output_report_path=str(report_path),
        original_docx_path=str(input_path),
    )

    print(f"Status: {report.get('status', 'failed')}")
    print(f"Metadata: {metadata_path}")
    print(f"Report: {report_path}")
    if formatted_path.exists():
        print(f"Formatted DOCX: {formatted_path}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
