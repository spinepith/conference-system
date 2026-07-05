from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conference_system.app.database import Base


class Conference(Base):
    __tablename__ = "conferences"

    conference_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    issues: Mapped[list["Issue"]] = relationship(back_populates="conference", cascade="all, delete-orphan")


class Issue(Base):
    __tablename__ = "issues"

    issue_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    conference_id: Mapped[str] = mapped_column(ForeignKey("conferences.conference_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conference: Mapped[Conference] = relationship(back_populates="issues")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="issue")


class Submission(Base):
    __tablename__ = "submissions"

    submission_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    conference_id: Mapped[str] = mapped_column(ForeignKey("conferences.conference_id"), nullable=False)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.issue_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(80), default="draft", index=True)
    author_contact: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    issue: Mapped[Issue] = relationship(back_populates="submissions")
    authors: Mapped[list["Author"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    files: Mapped[list["SubmissionFile"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    checks: Mapped[list["CheckResult"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    workflow_results: Mapped[list["WorkflowStageResult"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    status_history: Mapped[list["StatusHistory"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    editor_decisions: Mapped[list["EditorDecision"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    events: Mapped[list["EventLog"]] = relationship(back_populates="submission", cascade="all, delete-orphan")


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.submission_id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), default="")
    organization: Mapped[str] = mapped_column(String(300), default="")
    role: Mapped[str] = mapped_column(String(50), default="author")

    submission: Mapped[Submission] = relationship(back_populates="authors")


class SubmissionFile(Base):
    __tablename__ = "submission_files"
    __table_args__ = (UniqueConstraint("submission_id", "file_type", name="uq_submission_file_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.submission_id"), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(80), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(String(300), default="")
    mime_type: Mapped[str] = mapped_column(String(150), default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[Submission] = relationship(back_populates="files")


class CheckResult(Base):
    __tablename__ = "check_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.submission_id"), nullable=False, index=True)
    check_id: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(50), default="completed")
    risk_level: Mapped[str] = mapped_column(String(50), default="low")
    score: Mapped[float | None] = mapped_column(nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[Submission] = relationship(back_populates="checks")


class WorkflowStageResult(Base):
    __tablename__ = "workflow_stage_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.submission_id"), nullable=False, index=True)
    stage_id: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[Submission] = relationship(back_populates="workflow_results")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.submission_id"), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(80), default="")
    to_status: Mapped[str] = mapped_column(String(80), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(120), default="system")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    comment: Mapped[str] = mapped_column(Text, default="")

    submission: Mapped[Submission] = relationship(back_populates="status_history")


class EditorDecision(Base):
    __tablename__ = "editor_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.submission_id"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(80), nullable=False)
    editor_name: Mapped[str] = mapped_column(String(250), default="editor")
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[Submission] = relationship(back_populates="editor_decisions")


class EventLog(Base):
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.submission_id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped[Submission] = relationship(back_populates="events")
