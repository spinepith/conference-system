"""Manual PDF/ZIP demonstration for an existing submission directory."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tema.result_export.service import finalize_submission_files  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission_dir", help="Folder containing formatted_material.docx")
    args = parser.parse_args()
    print(finalize_submission_files(Path(args.submission_dir)))


if __name__ == "__main__":
    main()
