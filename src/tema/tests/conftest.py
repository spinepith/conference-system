from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

# Set environment before test modules import application code.
_TMP = tempfile.mkdtemp(prefix="conference_test_")
os.environ["CONFERENCE_DB_URL"] = f"sqlite:///{Path(_TMP) / 'test.db'}"
os.environ["CONFERENCE_STORAGE_DIR"] = str(Path(_TMP) / "storage")
os.environ["CONFERENCE_CREATE_DEMO_DATA"] = "0"


def _cleanup() -> None:
    shutil.rmtree(_TMP, ignore_errors=True)


atexit.register(_cleanup)
