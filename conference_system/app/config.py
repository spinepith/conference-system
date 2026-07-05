from __future__ import annotations

import os
from pathlib import Path


class Settings:
    """Runtime settings for the MVP application."""

    app_name: str = "Conference System MVP"
    db_url: str = os.getenv("CONFERENCE_DB_URL", "sqlite:///./storage/conference.db")
    storage_dir: Path = Path(os.getenv("CONFERENCE_STORAGE_DIR", "./storage"))
    create_demo_data: bool = os.getenv("CONFERENCE_CREATE_DEMO_DATA", "1") == "1"
    allowed_docx_ext: tuple[str, ...] = (".docx",)


settings = Settings()
