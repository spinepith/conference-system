from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
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
    SubmissionAuthor,
    SubmissionFile,
)
from .status_machine import assert_transition


EDITOR_DECISION_TO_STATUS = {
    "accept": "accepted",
    "reject": "rejected",
    "revision": "needs_revision",
    "return_to_author": "needs_author_review",
}


def _local_iso(value) -> str | None:
    if value is None:
        return None
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.isoformat()


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


def project_path_reference(path: str | Path) -> str:
    """Store project files portably relative to the repository root when possible."""
    resolved = Path(path).resolve()
    project_root = Path(settings.PROJECT_ROOT).resolve()
    try:
        return str(resolved.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def resolve_stored_file_path(value: str | Path) -> Path:
    """Resolve new project-relative and legacy core-relative file references."""
    path = Path(value)
    if path.is_absolute():
        return path

    project_candidate = Path(settings.PROJECT_ROOT) / path
    if project_candidate.exists():
        return project_candidate

    # Backward compatibility with records created before storage moved above src.
    legacy_candidate = Path(settings.BASE_DIR) / path
    if legacy_candidate.exists():
        return legacy_candidate
    return project_candidate


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
            SubmissionAuthor.objects.create(submission=submission, author=contact_author, order=1)

        for item in metadata.get("authors", []):
            if not isinstance(item, dict):
                continue
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
        if from_status == status:
            return self.get_submission(submission_id)
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

    @transaction.atomic
    def merge_extracted_metadata(self, submission_id: str, extracted: dict[str, Any]) -> dict[str, Any]:
        """Сохраняет полный результат DOCX-извлечения и дополняет канонические поля заявки.

        Поля, которые автор уже заполнил в форме, не перезаписываются пустыми или
        менее надёжными значениями парсера. Полный исходный результат всегда
        доступен в metadata["extracted_metadata"].
        """
        submission = Submission.objects.select_for_update().get(pk=submission_id)
        current = dict(submission.metadata or {})
        current["extracted_metadata"] = extracted

        mapping = {
            "title": "title_ru",
            "title_en": "title_en",
            "abstract": "abstract_ru",
            "abstract_en": "abstract_en",
            "keywords": "keywords_ru",
            "keywords_en": "keywords_en",
            "supervisor": "supervisor",
            "body_text": "body_text",
            "sections": "sections",
            "references": "references",
            "objects": "objects",
            "warnings": "extraction_warnings",
        }
        for source_key, target_key in mapping.items():
            value = extracted.get(source_key)
            if target_key in {"body_text", "sections", "references", "objects", "extraction_warnings"}:
                current[target_key] = value if value is not None else current.get(target_key)
            elif not current.get(target_key) and value:
                current[target_key] = value

        extracted_authors = extracted.get("authors") or []
        current["extracted_authors"] = extracted_authors
        if not current.get("authors") and extracted_authors:
            organization = extracted.get("organization") or submission.author_contact.get("organization", "")
            current["authors"] = [
                {"full_name": name, "organization": organization, "email": ""}
                for name in extracted_authors
                if isinstance(name, str) and name.strip()
            ]

        if not submission.author_contact.get("organization") and extracted.get("organization"):
            author_contact = dict(submission.author_contact or {})
            author_contact["organization"] = extracted["organization"]
            submission.author_contact = author_contact

        submission.metadata = current
        submission.save(update_fields=["metadata", "author_contact", "updated_at"])
        EventLog.objects.create(
            submission=submission,
            event_type="metadata_extracted",
            payload={
                "title": extracted.get("title", ""),
                "authors_count": len(extracted_authors),
                "warnings_count": len(extracted.get("warnings") or []),
            },
        )
        return self.get_submission(submission_id)

    @transaction.atomic
    def save_check_result(
        self,
        submission_id: str,
        check_result: dict[str, Any],
        *,
        replace_existing: bool = False,
    ) -> None:
        submission = Submission.objects.select_for_update().get(pk=submission_id)
        check_id = check_result.get("check_id", "unknown_check")
        if replace_existing:
            CheckResult.objects.filter(submission=submission, check_id=check_id).delete()
        CheckResult.objects.create(
            submission=submission,
            check_id=check_id,
            title=check_result.get("title", ""),
            status=check_result.get("status", "completed"),
            risk_level=check_result.get("risk_level", "low"),
            score=check_result.get("score"),
            summary=check_result.get("summary", ""),
            warnings=check_result.get("warnings", []),
            errors=check_result.get("errors", []),
            flagged_fragments=check_result.get("flagged_fragments", []),
            author_comment=check_result.get("author_comment", ""),
            editor_comment=check_result.get("editor_comment", ""),
            raw_model_response_path=check_result.get("raw_model_response_path", ""),
        )
        EventLog.objects.create(
            submission=submission,
            event_type="check_result_saved",
            payload={**check_result, "replaced_existing": replace_existing},
        )

    def add_event(self, submission_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        submission = Submission.objects.get(pk=submission_id)
        EventLog.objects.create(submission=submission, event_type=event_type, payload=payload or {})

    def save_uploaded_file(self, submission: Submission, file_type: str, uploaded_file: UploadedFile) -> SubmissionFile:
        destination_dir = Path(settings.SUBMISSIONS_STORAGE_DIR) / submission.submission_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(uploaded_file.name or "uploaded.docx").name
        if file_type == "original_docx":
            safe_name = "original.docx"
        elif file_type == "revision_docx":
            safe_name = f"revision_{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}.docx"
        path = destination_dir / safe_name
        with path.open("wb") as fh:
            for chunk in uploaded_file.chunks():
                fh.write(chunk)
        relative_path = project_path_reference(path)
        file_row = SubmissionFile.objects.create(submission=submission, file_type=file_type, path=relative_path)
        EventLog.objects.create(
            submission=submission,
            event_type="file_saved",
            payload={"file_type": file_type, "path": relative_path},
        )
        return file_row

    @transaction.atomic
    def save_or_update_file_path(self, submission_id: str, file_type: str, path: str) -> dict[str, Any]:
        """Сохраняет путь результата обработки, заменяя старую запись того же типа."""
        submission = Submission.objects.select_for_update().get(pk=submission_id)
        normalized_path = project_path_reference(path) if Path(path).is_absolute() else str(path).replace("\\", "/")
        file_row = SubmissionFile.objects.filter(submission=submission, file_type=file_type).order_by("-uploaded_at", "-id").first()
        if file_row:
            file_row.path = normalized_path
            file_row.save(update_fields=["path"])
            SubmissionFile.objects.filter(submission=submission, file_type=file_type).exclude(pk=file_row.pk).delete()
        else:
            file_row = SubmissionFile.objects.create(submission=submission, file_type=file_type, path=normalized_path)
        EventLog.objects.create(
            submission=submission,
            event_type="file_path_saved",
            payload={"file_type": file_type, "path": normalized_path},
        )
        return {"id": file_row.id, "file_type": file_row.file_type, "path": file_row.path}

    def save_file_path(self, submission_id: str, file_type: str, path: str) -> dict[str, Any]:
        return self.save_or_update_file_path(submission_id, file_type, path)

    def get_latest_file_path(self, submission_id: str, file_type: str) -> str:
        row = SubmissionFile.objects.filter(submission_id=submission_id, file_type=file_type).order_by("-uploaded_at", "-id").first()
        return row.path if row else ""

    def save_editor_decision(self, submission_id: str, decision: str, editor_name: str = "editor", comment: str = "") -> dict[str, Any]:
        submission = Submission.objects.get(pk=submission_id)
        row = EditorDecision.objects.create(
            submission=submission,
            decision=decision,
            editor_name=editor_name,
            comment=comment,
        )
        EventLog.objects.create(
            submission=submission,
            event_type="editor_decision_saved",
            payload={"decision": decision, "editor_name": editor_name, "comment": comment},
        )
        return {
            "id": row.id,
            "decision": row.decision,
            "editor_name": row.editor_name,
            "comment": row.comment,
        }

    @transaction.atomic
    def apply_editor_decision(
        self,
        submission_id: str,
        decision: str,
        editor_name: str = "editor",
        comment: str = "",
    ) -> dict[str, Any]:
        """Atomically save a human editor decision and its resulting status.

        Generic workflow transitions are intentionally strict. An editor, however,
        must be able to correct or replace an earlier human decision (for example,
        change ``needs_revision`` to ``accepted``) without manually rebuilding an
        intermediate status chain. Published and issue-included materials keep
        their stronger safeguards.
        """
        target_status = EDITOR_DECISION_TO_STATUS.get(decision)
        if not target_status:
            raise ValueError("Неизвестное решение редактора.")

        submission = Submission.objects.select_for_update().get(pk=submission_id)
        from_status = submission.status
        if from_status == "published":
            raise ValueError("Опубликованный материал нельзя изменить без отмены публикации.")
        if from_status == "included_in_issue":
            raise ValueError("Сначала исключите материал из выпуска.")

        if from_status != target_status:
            submission.status = target_status
            submission.save(update_fields=["status", "updated_at"])
            StatusHistory.objects.create(
                submission=submission,
                from_status=from_status,
                to_status=target_status,
                changed_by=editor_name,
                comment=comment,
            )
            EventLog.objects.create(
                submission=submission,
                event_type="status_changed",
                payload={
                    "from_status": from_status,
                    "to_status": target_status,
                    "comment": comment,
                    "source": "editor_decision",
                },
            )

        row = EditorDecision.objects.create(
            submission=submission,
            decision=decision,
            editor_name=editor_name,
            comment=comment,
        )
        EventLog.objects.create(
            submission=submission,
            event_type="editor_decision_saved",
            payload={
                "decision": decision,
                "editor_name": editor_name,
                "comment": comment,
                "status": target_status,
            },
        )
        return {
            "id": row.id,
            "decision": row.decision,
            "editor_name": row.editor_name,
            "comment": row.comment,
            "status": target_status,
        }

    @staticmethod
    def _latest_files(submission: Submission) -> dict[str, str]:
        result: dict[str, str] = {}
        rows = sorted(
            submission.files.all(),
            key=lambda row: (row.uploaded_at, row.id),
            reverse=True,
        )
        for row in rows:
            result.setdefault(row.file_type, row.path)
        return result

    def to_dict(self, submission: Submission, compact: bool = False) -> dict[str, Any]:
        data = {
            "submission_id": submission.submission_id,
            "conference_id": submission.conference_id,
            "issue_id": submission.issue_id,
            "status": submission.status,
            "created_at": _local_iso(submission.created_at),
            "updated_at": _local_iso(submission.updated_at),
            "author_contact": submission.author_contact,
            "metadata": submission.metadata,
            "authors": [
                {
                    "full_name": row.full_name,
                    "organization": row.organization.name if row.organization else "",
                    "email": row.email,
                }
                for row in submission.authors.all()
            ],
            "files": self._latest_files(submission),
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
                    "flagged_fragments": row.flagged_fragments,
                    "author_comment": row.author_comment,
                    "editor_comment": row.editor_comment,
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
                "status_history": [
                    {
                        "from_status": row.from_status,
                        "to_status": row.to_status,
                        "changed_by": row.changed_by,
                        "changed_at": _local_iso(row.changed_at),
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
                        "started_at": _local_iso(row.started_at),
                        "finished_at": _local_iso(row.finished_at),
                    }
                    for row in submission.workflow_results.all()
                ],
                "events": [
                    {"event_type": row.event_type, "payload": row.payload, "created_at": _local_iso(row.created_at)}
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
                "created_at": _local_iso(last_decision.created_at),
            }
        return data


def save_json_file(submission_id: str, filename: str, payload: dict[str, Any]) -> str:
    destination_dir = Path(settings.SUBMISSIONS_STORAGE_DIR) / submission_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    path = destination_dir / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return project_path_reference(path)
