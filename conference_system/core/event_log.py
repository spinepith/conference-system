from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from conference_system.core.models import EventLog


def add_event(db: Session, submission_id: str, event_type: str, payload: dict[str, Any] | None = None) -> EventLog:
    event = EventLog(submission_id=submission_id, event_type=event_type, payload=payload or {})
    db.add(event)
    return event
