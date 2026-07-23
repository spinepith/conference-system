"""Run the Django management command that creates a five-material test issue."""
from __future__ import annotations

import os
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_ROOT = SRC_ROOT / "system"
for path in (str(SRC_ROOT), str(SYSTEM_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conference_project.settings")

import django  # noqa: E402
from django.core.management import call_command  # noqa: E402


def main() -> None:
    django.setup()
    call_command("create_test_issue")


if __name__ == "__main__":
    main()
