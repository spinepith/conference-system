from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AuthorContact(BaseModel):
    full_name: str = Field(..., min_length=2)
    email: str
    organization: str = ""


class AuthorIn(BaseModel):
    full_name: str
    organization: str = ""
    email: str = ""


class SubmissionMetadata(BaseModel):
    title_ru: str = Field(..., min_length=2)
    title_en: str = ""
    authors: list[AuthorIn] = Field(default_factory=list)
    supervisor: str = ""
    section: str = ""
    keywords_ru: list[str] = Field(default_factory=list)
    abstract_ru: str = ""


class SubmissionCreate(BaseModel):
    conference_id: str = "ai_quarterly_conf"
    issue_id: str = "2026_q1"
    author_contact: AuthorContact
    metadata: SubmissionMetadata


class StatusUpdate(BaseModel):
    status: str
    comment: str = ""
    changed_by: str = "system"


class CheckResultIn(BaseModel):
    check_id: str
    title: str = ""
    status: str = "completed"
    risk_level: str = "low"
    score: float | None = None
    summary: str = ""
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    raw_model_response_path: str = ""


class EventIn(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EditorDecisionIn(BaseModel):
    decision: str
    editor_name: str = "editor"
    comment: str = ""
