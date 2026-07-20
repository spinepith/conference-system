"""Compatibility entry point for the independent DOCX module.

Workflow classes belong to the main Django module and are implemented in
``src/system/submissions/integrations/docx_stages.py``.  The DOCX package
remains framework-neutral and exposes only service functions here.
"""

from docx_processing.service import (
    extract_metadata,
    format_to_template,
    load_extracted_metadata,
    process_submission,
    save_extracted_metadata,
)

__all__ = [
    "extract_metadata",
    "format_to_template",
    "load_extracted_metadata",
    "process_submission",
    "save_extracted_metadata",
]
