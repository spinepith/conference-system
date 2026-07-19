from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from .models import (
    Author,
    CheckResult,
    Conference,
    EditorDecision,
    EventLog,
    Issue,
    Organization,
    StatusHistory,
    Submission,
    SubmissionFile,
    SubmissionAuthor,
)
from .status_machine import assert_transition


def clean_organization_name(name: str) -> str:
    return " ".join((name or "").split())


def normalize_organization_name(name: str) -> str:
    return clean_organization_name(name).casefold()


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in (value or "").replace(";", ",").split(",") if part.strip()]


def load_seed_organizations() -> list[str]:
    path = Path(settings.ORGANIZATIONS_SEED_PATH)
    if not path.exists():
        return []
    result: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        name = clean_organization_name(line)
        key = normalize_organization_name(name)
        if name and key not in seen:
            seen.add(key)
            result.append(name)
    return result


class SubmissionService:
    def ensure_defaults(self) -> None:
        conference, _ = Conference.objects.get_or_create(
            conference_id=settings.CONFERENCE_DEFAULT_ID,
            defaults={
                "title": "Постоянно действующая научная конференция по искусственному интеллекту",
                "description": "MVP конференционной системы",
            },
        )
        Issue.objects.get_or_create(
            issue_id=settings.ISSUE_DEFAULT_ID,
            defaults={
                "conference": conference,
                "title": "Искусственный интеллект и цифровые технологии: материалы конференции",
                "year": 2026,
                "quarter": 1,
            },
        )
        self.seed_organizations()

    def seed_organizations(self) -> None:
        if Organization.objects.exists():
            return
        rows = [
            Organization(name=name, normalized_name=normalize_organization_name(name), source="seed")
            for name in load_seed_organizations()
        ]
        if rows:
            Organization.objects.bulk_create(rows, ignore_conflicts=True)

    def ensure_organization(
        self,
        name: str,
        source: str = "user",
        created_by_submission: Submission | None = None,
    ) -> Organization | None:
        clean_name = clean_organization_name(name)
        if not clean_name:
            return None
        normalized = normalize_organization_name(clean_name)
        organization, created = Organization.objects.get_or_create(
            normalized_name=normalized,
            defaults={
                "name": clean_name,
                "source": source,
                "created_by_submission": created_by_submission,
            },
        )
        if not created and not organization.name:
            organization.name = clean_name
            organization.save(update_fields=["name"])
        return organization

    def list_organizations(self, q: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        self.ensure_defaults()
        qs = Organization.objects.all()
        if q:
            qs = qs.filter(name__icontains=q.strip())
        limit = min(max(int(limit or 50), 1), 500)
        return [{"id": row.id, "name": row.name, "source": row.source} for row in qs.order_by("name")[:limit]]

    def _next_submission_id(self, issue_id: str) -> str:
        issue_part = issue_id.upper().replace("_", "-")
        count = Submission.objects.filter(issue_id=issue_id).count() + 1
        return f"SUB-{issue_part}-{count:05d}"

    @transaction.atomic
    def create_submission(self, data: dict[str, Any], uploaded_file: UploadedFile | None = None) -> dict[str, Any]:
        self.ensure_defaults()
        conference_id = data.get("conference_id") or settings.CONFERENCE_DEFAULT_ID
        issue_id = data.get("issue_id") or settings.ISSUE_DEFAULT_ID
        conference = Conference.objects.get(pk=conference_id)
        issue = Issue.objects.get(pk=issue_id)
        submission_id = self._next_submission_id(issue_id)

        author_contact = data.get("author_contact") or {}
        metadata = data.get("metadata") or {}
        organization_name = author_contact.get("organization") or ""

        submission = Submission.objects.create(
            submission_id=submission_id,
            conference=conference,
            issue=issue,
            status="uploaded",
            author_contact=author_contact,
            metadata=metadata,
        )
        self.ensure_organization(organization_name, source="user", created_by_submission=submission)

        contact_name = author_contact.get("full_name") or ""
        if contact_name:
            contact_org = self.ensure_organization(
                organization_name,
                source="user",
                created_by_submission=submission,
            )
            contact_author = Author.objects.create(
                full_name=contact_name,
                organization=contact_org,
                email=author_contact.get("email", ""),
            )
            SubmissionAuthor.objects.create(
                submission=submission,
                author=contact_author,
                order=1,
            )
        for item in metadata.get("authors", []):
            name = item.get("full_name") or ""
            if name and name != contact_name:
                author_org = self.ensure_organization(
                    item.get("organization", organization_name),
                    source="user",
                    created_by_submission=submission,
                )
                author = Author.objects.create(
                    full_name=name,
                    organization=author_org,
                    email=item.get("email", ""),
                )
                SubmissionAuthor.objects.create(
                    submission=submission,
                    author=author,
                    order=SubmissionAuthor.objects.filter(submission=submission).count() + 1,
                )
                self.ensure_organization(item.get("organization", ""), source="user", created_by_submission=submission)

        StatusHistory.objects.create(
            submission=submission,
            from_status="",
            to_status="uploaded",
            changed_by="system",
            comment="Заявка создана, файл загружен." if uploaded_file else "Заявка создана.",
        )
        EventLog.objects.create(submission=submission, event_type="submission_created", payload={"source": "django"})

        if uploaded_file is not None:
            self.save_uploaded_file(submission, "original_docx", uploaded_file)
        return self.get_submission(submission_id)

    def create_submission_from_form(self, cleaned: dict[str, Any], uploaded_file: UploadedFile) -> dict[str, Any]:
        organization = clean_organization_name(cleaned.get("organization") or "")
        authors = cleaned.get("authors_json") or []
        data = {
            "conference_id": settings.CONFERENCE_DEFAULT_ID,
            "issue_id": settings.ISSUE_DEFAULT_ID,
            "author_contact": {
                "full_name": cleaned["full_name"],
                "email": cleaned["email"],
                "organization": organization,
            },
            "metadata": {
                "title_ru": cleaned["title_ru"],
                "title_en": "",
                "authors": authors,
                "supervisor": cleaned.get("supervisor", ""),
                "section": cleaned.get("section", ""),
                "keywords_ru": split_csv(cleaned.get("keywords_ru", "")),
                "abstract_ru": cleaned.get("abstract_ru", ""),
            },
        }
        return self.create_submission(data, uploaded_file=uploaded_file)

    def get_submission_model(self, submission_id: str) -> Submission:
        return Submission.objects.prefetch_related(
            "authors",
            "files",
            "checks",
            "workflow_results",
            "status_history",
            "editor_decisions",
            "events",
        ).get(pk=submission_id)

    def get_submission(self, submission_id: str) -> dict[str, Any]:
        return self.to_dict(self.get_submission_model(submission_id))

    def list_submissions(self, issue_id: str | None = None) -> list[dict[str, Any]]:
        self.ensure_defaults()
        qs = Submission.objects.prefetch_related("files", "checks")
        if issue_id:
            qs = qs.filter(issue_id=issue_id)
        return [self.to_dict(row, compact=True) for row in qs]

    @transaction.atomic
    def update_submission_status(
        self,
        submission_id: str,
        status: str,
        comment: str = "",
        changed_by: str = "system",
    ) -> dict[str, Any]:
        submission = Submission.objects.select_for_update().get(pk=submission_id)
        from_status = submission.status
        assert_transition(from_status, status)
        submission.status = status
        submission.save(update_fields=["status", "updated_at"])
        StatusHistory.objects.create(
            submission=submission,
            from_status=from_status,
            to_status=status,
            changed_by=changed_by,
            comment=comment,
        )
        EventLog.objects.create(
            submission=submission,
            event_type="status_changed",
            payload={"from_status": from_status, "to_status": status, "comment": comment},
        )
        return self.get_submission(submission_id)

    def save_check_result(self, submission_id: str, check_result: dict[str, Any]) -> None:
        submission = Submission.objects.get(pk=submission_id)
        CheckResult.objects.create(
            submission=submission,
            check_id=check_result.get("check_id", "unknown_check"),
            title=check_result.get("title", ""),
            status=check_result.get("status", "completed"),
            risk_level=check_result.get("risk_level", "low"),
            score=check_result.get("score"),
            summary=check_result.get("summary", ""),
            warnings=check_result.get("warnings", []),
            errors=check_result.get("errors", []),
            raw_model_response_path=check_result.get("raw_model_response_path", ""),
        )
        EventLog.objects.create(submission=submission, event_type="check_result_saved", payload=check_result)

    def add_event(self, submission_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        submission = Submission.objects.get(pk=submission_id)
        EventLog.objects.create(submission=submission, event_type=event_type, payload=payload or {})

    def save_uploaded_file(self, submission: Submission, file_type: str, uploaded_file: UploadedFile) -> SubmissionFile:
        destination_dir = Path(settings.MEDIA_ROOT) / "submissions" / submission.submission_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_name = uploaded_file.name or "uploaded.docx"
        if file_type == "original_docx":
            safe_name = "original.docx"
        elif file_type == "revision_docx":
            safe_name = f"revision_{timezone.now().strftime('%Y%m%d_%H%M%S')}.docx"
        path = destination_dir / safe_name
        with path.open("wb") as fh:
            for chunk in uploaded_file.chunks():
                fh.write(chunk)
        relative_path = str(path.relative_to(Path(settings.BASE_DIR))).replace("\\", "/")
        file_row = SubmissionFile.objects.create(submission=submission, file_type=file_type, path=relative_path)
        EventLog.objects.create(submission=submission, event_type="file_saved", payload={"file_type": file_type, "path": relative_path})
        return file_row

    def save_file_path(self, submission_id: str, file_type: str, path: str) -> dict[str, Any]:
        submission = Submission.objects.get(pk=submission_id)
        file_row = SubmissionFile.objects.create(submission=submission, file_type=file_type, path=path)
        EventLog.objects.create(submission=submission, event_type="file_path_saved", payload={"file_type": file_type, "path": path})
        return {"id": file_row.id, "file_type": file_row.file_type, "path": file_row.path}

    def save_editor_decision(self, submission_id: str, decision: str, editor_name: str = "editor", comment: str = "") -> dict[str, Any]:
        submission = Submission.objects.get(pk=submission_id)
        row = EditorDecision.objects.create(submission=submission, decision=decision, editor_name=editor_name, comment=comment)
        EventLog.objects.create(
            submission=submission,
            event_type="editor_decision_saved",
            payload={"decision": decision, "editor_name": editor_name, "comment": comment},
        )
        return {"id": row.id, "decision": row.decision, "editor_name": row.editor_name, "comment": row.comment}

    def to_dict(self, submission: Submission, compact: bool = False) -> dict[str, Any]:
        data = {
            "submission_id": submission.submission_id,
            "conference_id": submission.conference_id,
            "issue_id": submission.issue_id,
            "status": submission.status,
            "created_at": submission.created_at.isoformat(),
            "updated_at": submission.updated_at.isoformat(),
            "author_contact": submission.author_contact,
            "metadata": submission.metadata,
            "files": {row.file_type: row.path for row in submission.files.all()},
            "checks": [
                {
                    "check_id": row.check_id,
                    "title": row.title,
                    "status": row.status,
                    "risk_level": row.risk_level,
                    "score": row.score,
                    "summary": row.summary,
                    "warnings": row.warnings,
                    "errors": row.errors,
                    "raw_model_response_path": row.raw_model_response_path,
                }
                for row in submission.checks.all()
            ],
            "editor_decision": None,
        }
        if compact:
            return data
        data.update(
            {
                "authors": [
                    {"full_name": row.full_name, "organization": row.organization.name if row.organization else "", "email": row.email}
                    for row in submission.authors.all()
                ],
                "status_history": [
                    {
                        "from_status": row.from_status,
                        "to_status": row.to_status,
                        "changed_by": row.changed_by,
                        "changed_at": row.changed_at.isoformat(),
                        "comment": row.comment,
                    }
                    for row in submission.status_history.all()
                ],
                "workflow_results": [
                    {
                        "stage_id": row.stage_id,
                        "title": row.title,
                        "status": row.status,
                        "message": row.message,
                        "result": row.result_json,
                    }
                    for row in submission.workflow_results.all()
                ],
                "events": [
                    {"event_type": row.event_type, "payload": row.payload, "created_at": row.created_at.isoformat()}
                    for row in submission.events.all()
                ],
            }
        )
        last_decision = submission.editor_decisions.first()
        if last_decision:
            data["editor_decision"] = {
                "decision": last_decision.decision,
                "editor_name": last_decision.editor_name,
                "comment": last_decision.comment,
                "created_at": last_decision.created_at.isoformat(),
            }
        return data


def save_json_file(submission_id: str, filename: str, payload: dict[str, Any]) -> str:
    destination_dir = Path(settings.MEDIA_ROOT) / "submissions" / submission_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    path = destination_dir / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.relative_to(Path(settings.BASE_DIR))).replace("\\", "/")
