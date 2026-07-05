from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from conference_system.core.event_log import add_event as add_event_row
from conference_system.core.file_storage import save_json, save_upload
from conference_system.core.models import (
    Author,
    CheckResult,
    Conference,
    EditorDecision,
    Issue,
    StatusHistory,
    Submission,
    SubmissionFile,
    WorkflowStageResult,
)
from conference_system.core.status_machine import assert_transition, validate_status
from conference_system.submissions.repository import SubmissionRepository


class SubmissionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SubmissionRepository(db)

    def ensure_defaults(self) -> None:
        conference = self.db.get(Conference, "ai_quarterly_conf")
        if not conference:
            conference = Conference(
                conference_id="ai_quarterly_conf",
                title="Постоянно действующая научная конференция по искусственному интеллекту",
                description="MVP конференционной системы",
            )
            self.db.add(conference)
        issue = self.db.get(Issue, "2026_q1")
        if not issue:
            issue = Issue(
                issue_id="2026_q1",
                conference_id="ai_quarterly_conf",
                title="Искусственный интеллект и цифровые технологии: материалы конференции",
                year=2026,
                quarter=1,
            )
            self.db.add(issue)
        self.db.commit()

    def create_submission(self, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_defaults()
        issue_id = data.get("issue_id") or "2026_q1"
        conference_id = data.get("conference_id") or "ai_quarterly_conf"
        number = self.repo.next_number_for_issue(issue_id)
        year = issue_id.split("_")[0] if "_" in issue_id else datetime.utcnow().strftime("%Y")
        quarter = issue_id.split("_")[1].upper() if "_" in issue_id else "Q1"
        submission_id = f"SUB-{year}-{quarter}-{number:05d}"

        author_contact = data.get("author_contact") or {}
        metadata = data.get("metadata") or {}
        authors = metadata.get("authors") or []
        if not authors and author_contact.get("full_name"):
            authors = [
                {
                    "full_name": author_contact.get("full_name", ""),
                    "email": author_contact.get("email", ""),
                    "organization": author_contact.get("organization", ""),
                }
            ]
            metadata["authors"] = authors

        submission = Submission(
            submission_id=submission_id,
            conference_id=conference_id,
            issue_id=issue_id,
            status="draft",
            author_contact=author_contact,
            metadata_json=metadata,
        )
        self.db.add(submission)
        for idx, item in enumerate(authors):
            self.db.add(
                Author(
                    submission_id=submission_id,
                    full_name=item.get("full_name", ""),
                    email=item.get("email", ""),
                    organization=item.get("organization", ""),
                    role="contact" if idx == 0 else "author",
                )
            )
        self.db.add(
            StatusHistory(
                submission_id=submission_id,
                from_status="",
                to_status="draft",
                changed_by="system",
                comment="Заявка создана.",
            )
        )
        add_event_row(self.db, submission_id, "submission_created", {"submission_id": submission_id})
        self.db.commit()
        return self.get_submission(submission_id)

    def get_submission(self, submission_id: str) -> dict[str, Any]:
        submission = self.repo.get(submission_id)
        if not submission:
            raise KeyError(f"Submission {submission_id!r} not found")
        return self.to_dict(submission)

    def list_submissions(self, issue_id: str | None = None) -> list[dict[str, Any]]:
        return [self.to_short_dict(item) for item in self.repo.list(issue_id)]

    def update_submission_status(
        self,
        submission_id: str,
        status: str,
        comment: str = "",
        changed_by: str = "system",
        strict: bool = False,
    ) -> dict[str, Any]:
        validate_status(status)
        submission = self.repo.get(submission_id)
        if not submission:
            raise KeyError(f"Submission {submission_id!r} not found")
        from_status = submission.status
        if strict:
            assert_transition(from_status, status)
        submission.status = status
        submission.updated_at = datetime.utcnow()
        self.db.add(
            StatusHistory(
                submission_id=submission_id,
                from_status=from_status,
                to_status=status,
                changed_by=changed_by,
                comment=comment,
            )
        )
        add_event_row(
            self.db,
            submission_id,
            "status_changed",
            {"from_status": from_status, "to_status": status, "comment": comment, "changed_by": changed_by},
        )
        self.db.commit()
        return self.get_submission(submission_id)

    def save_submission_file(
        self,
        submission_id: str,
        file_type: str,
        path: str,
        original_name: str = "",
        mime_type: str = "",
    ) -> dict[str, Any]:
        if not self.repo.get(submission_id):
            raise KeyError(f"Submission {submission_id!r} not found")
        existing = (
            self.db.query(SubmissionFile)
            .filter(SubmissionFile.submission_id == submission_id, SubmissionFile.file_type == file_type)
            .one_or_none()
        )
        if existing:
            existing.path = path
            existing.original_name = original_name
            existing.mime_type = mime_type
            existing.uploaded_at = datetime.utcnow()
        else:
            self.db.add(
                SubmissionFile(
                    submission_id=submission_id,
                    file_type=file_type,
                    path=path,
                    original_name=original_name,
                    mime_type=mime_type,
                )
            )
        add_event_row(
            self.db,
            submission_id,
            "file_saved",
            {"file_type": file_type, "path": path, "original_name": original_name},
        )
        self.db.commit()
        return self.get_submission(submission_id)

    def save_upload_file(self, submission_id: str, file_type: str, file_obj, original_name: str, mime_type: str = "") -> dict[str, Any]:
        path = save_upload(submission_id, file_type, file_obj, original_name)
        result = self.save_submission_file(submission_id, file_type, path, original_name, mime_type)
        if file_type == "original_docx" and result["status"] == "draft":
            result = self.update_submission_status(submission_id, "uploaded", "DOCX-файл загружен.", "author")
        elif file_type == "revision_docx":
            result = self.update_submission_status(submission_id, "uploaded", "Автор загрузил исправленную версию.", "author")
        return result

    def save_check_result(self, submission_id: str, check_result: dict[str, Any]) -> None:
        if not self.repo.get(submission_id):
            raise KeyError(f"Submission {submission_id!r} not found")
        row = CheckResult(
            submission_id=submission_id,
            check_id=check_result.get("check_id", "unknown_check"),
            title=check_result.get("title", ""),
            status=check_result.get("status", "completed"),
            risk_level=check_result.get("risk_level", "low"),
            score=check_result.get("score"),
            summary=check_result.get("summary", ""),
            result_json=check_result,
        )
        self.db.add(row)
        # Keep latest report as JSON file for downloads and interoperability.
        path = save_json(submission_id, "check_report", check_result)
        self.save_submission_file(submission_id, "check_report", path, "check_report.json", "application/json")
        add_event_row(self.db, submission_id, "check_result_saved", check_result)
        self.db.commit()

    def save_workflow_stage_result(self, submission_id: str, stage_result: dict[str, Any]) -> None:
        if not self.repo.get(submission_id):
            raise KeyError(f"Submission {submission_id!r} not found")
        self.db.add(
            WorkflowStageResult(
                submission_id=submission_id,
                stage_id=stage_result.get("stage_id", "unknown_stage"),
                title=stage_result.get("title", ""),
                status=stage_result.get("status", "success"),
                message=stage_result.get("message", ""),
                result_json=stage_result,
            )
        )
        add_event_row(self.db, submission_id, "workflow_stage_result_saved", stage_result)
        self.db.commit()

    def add_event(self, submission_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if not self.repo.get(submission_id):
            raise KeyError(f"Submission {submission_id!r} not found")
        add_event_row(self.db, submission_id, event_type, payload)
        self.db.commit()

    def save_editor_decision(self, submission_id: str, decision: str, editor_name: str = "editor", comment: str = "") -> dict[str, Any]:
        if not self.repo.get(submission_id):
            raise KeyError(f"Submission {submission_id!r} not found")
        self.db.add(
            EditorDecision(submission_id=submission_id, decision=decision, editor_name=editor_name, comment=comment)
        )
        decision_to_status = {
            "accept": "accepted",
            "accepted": "accepted",
            "reject": "rejected",
            "rejected": "rejected",
            "revision": "needs_revision",
            "needs_revision": "needs_revision",
        }
        target = decision_to_status.get(decision)
        if target:
            self.update_submission_status(submission_id, target, comment or f"Решение редактора: {decision}", editor_name)
        else:
            self.db.commit()
        return self.get_submission(submission_id)

    @staticmethod
    def to_short_dict(submission: Submission) -> dict[str, Any]:
        return {
            "submission_id": submission.submission_id,
            "conference_id": submission.conference_id,
            "issue_id": submission.issue_id,
            "status": submission.status,
            "created_at": submission.created_at.isoformat(),
            "updated_at": submission.updated_at.isoformat(),
            "author_contact": submission.author_contact,
            "metadata": submission.metadata_json,
            "files": {file.file_type: file.path for file in submission.files},
            "checks_count": len(submission.checks),
        }

    @staticmethod
    def to_dict(submission: Submission) -> dict[str, Any]:
        return {
            "submission_id": submission.submission_id,
            "conference_id": submission.conference_id,
            "issue_id": submission.issue_id,
            "status": submission.status,
            "created_at": submission.created_at.isoformat(),
            "updated_at": submission.updated_at.isoformat(),
            "author_contact": submission.author_contact,
            "metadata": submission.metadata_json,
            "authors": [
                {
                    "full_name": author.full_name,
                    "email": author.email,
                    "organization": author.organization,
                    "role": author.role,
                }
                for author in submission.authors
            ],
            "files": {file.file_type: file.path for file in submission.files},
            "file_details": [
                {
                    "file_type": file.file_type,
                    "path": file.path,
                    "original_name": file.original_name,
                    "mime_type": file.mime_type,
                    "uploaded_at": file.uploaded_at.isoformat(),
                }
                for file in submission.files
            ],
            "checks": [
                {
                    "check_id": check.check_id,
                    "title": check.title,
                    "status": check.status,
                    "risk_level": check.risk_level,
                    "score": check.score,
                    "summary": check.summary,
                    "result": check.result_json,
                    "created_at": check.created_at.isoformat(),
                }
                for check in submission.checks
            ],
            "workflow_results": [
                {
                    "stage_id": item.stage_id,
                    "title": item.title,
                    "status": item.status,
                    "message": item.message,
                    "result": item.result_json,
                    "started_at": item.started_at.isoformat(),
                    "finished_at": item.finished_at.isoformat(),
                }
                for item in submission.workflow_results
            ],
            "status_history": [
                {
                    "from_status": item.from_status,
                    "to_status": item.to_status,
                    "changed_by": item.changed_by,
                    "changed_at": item.changed_at.isoformat(),
                    "comment": item.comment,
                }
                for item in submission.status_history
            ],
            "editor_decision": (
                {
                    "decision": submission.editor_decisions[-1].decision,
                    "editor_name": submission.editor_decisions[-1].editor_name,
                    "comment": submission.editor_decisions[-1].comment,
                    "created_at": submission.editor_decisions[-1].created_at.isoformat(),
                }
                if submission.editor_decisions
                else None
            ),
            "events": [
                {"event_type": event.event_type, "payload": event.payload, "created_at": event.created_at.isoformat()}
                for event in submission.events
            ],
        }


def create_submission(data: dict[str, Any]) -> dict[str, Any]:
    from conference_system.app.database import SessionLocal

    with SessionLocal() as db:
        return SubmissionService(db).create_submission(data)


def get_submission(submission_id: str) -> dict[str, Any]:
    from conference_system.app.database import SessionLocal

    with SessionLocal() as db:
        return SubmissionService(db).get_submission(submission_id)


def list_submissions(issue_id: str | None = None) -> list[dict[str, Any]]:
    from conference_system.app.database import SessionLocal

    with SessionLocal() as db:
        return SubmissionService(db).list_submissions(issue_id)


def update_submission_status(submission_id: str, status: str, comment: str) -> dict[str, Any]:
    from conference_system.app.database import SessionLocal

    with SessionLocal() as db:
        return SubmissionService(db).update_submission_status(submission_id, status, comment)


def save_check_result(submission_id: str, check_result: dict[str, Any]) -> None:
    from conference_system.app.database import SessionLocal

    with SessionLocal() as db:
        SubmissionService(db).save_check_result(submission_id, check_result)


def add_event(submission_id: str, event_type: str, payload: dict[str, Any]) -> None:
    from conference_system.app.database import SessionLocal

    with SessionLocal() as db:
        SubmissionService(db).add_event(submission_id, event_type, payload)
