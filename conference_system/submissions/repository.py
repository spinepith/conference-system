from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from conference_system.core.models import Submission


class SubmissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def next_number_for_issue(self, issue_id: str) -> int:
        count = self.db.scalar(select(func.count()).select_from(Submission).where(Submission.issue_id == issue_id))
        return int(count or 0) + 1

    def get(self, submission_id: str) -> Submission | None:
        return self.db.scalar(
            select(Submission)
            .where(Submission.submission_id == submission_id)
            .options(
                selectinload(Submission.authors),
                selectinload(Submission.files),
                selectinload(Submission.checks),
                selectinload(Submission.workflow_results),
                selectinload(Submission.status_history),
                selectinload(Submission.editor_decisions),
                selectinload(Submission.events),
            )
        )

    def list(self, issue_id: str | None = None) -> list[Submission]:
        stmt = select(Submission).options(selectinload(Submission.files), selectinload(Submission.checks))
        if issue_id:
            stmt = stmt.where(Submission.issue_id == issue_id)
        stmt = stmt.order_by(Submission.created_at.desc())
        return list(self.db.scalars(stmt))
