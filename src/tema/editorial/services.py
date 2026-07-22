from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction

from submissions.models import Conference, Issue, Submission
from submissions.services import (
    SubmissionService,
    project_path_reference,
    resolve_stored_file_path,
)
from submissions.status_machine import assert_transition

from ..issue_builder.archive_page import build_archive_html, save_archive_html
from ..issue_builder.collection_builder import build_collection_pdf
from ..issue_builder.toc_builder import group_by_section
from ..result_export.service import finalize_submission_files
from .models import IssueExtras

COLLECTION_FILENAME = "collection.pdf"
ARCHIVE_FILENAME = "index.html"


def get_issues_dir(issue_id: str) -> Path:
    path = Path(settings.ISSUES_STORAGE_DIR) / issue_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_issue_row(issue_id: str) -> Issue:
    try:
        return Issue.objects.select_related("conference").get(pk=issue_id)
    except Issue.DoesNotExist as exc:
        raise KeyError(f"Выпуск {issue_id!r} не найден") from exc


def _get_or_create_extras(issue: Issue) -> IssueExtras:
    extras, _ = IssueExtras.objects.get_or_create(issue=issue)
    return extras


@transaction.atomic
def create_issue(data: dict[str, Any]) -> Issue:
    issue_id = str(data["issue_id"]).strip()
    if not issue_id:
        raise ValueError("Не указан идентификатор выпуска.")
    if Issue.objects.filter(pk=issue_id).exists():
        raise ValueError(f"Выпуск {issue_id!r} уже существует")
    conference_id = data.get("conference_id") or settings.CONFERENCE_DEFAULT_ID
    try:
        conference = Conference.objects.get(pk=conference_id)
    except Conference.DoesNotExist as exc:
        raise ValueError(f"Конференция {conference_id!r} не найдена") from exc
    quarter = int(data["quarter"])
    if quarter not in {1, 2, 3, 4}:
        raise ValueError("Квартал должен быть от 1 до 4.")
    issue = Issue.objects.create(
        issue_id=issue_id,
        conference=conference,
        title=str(data["title"]).strip(),
        year=int(data["year"]),
        quarter=quarter,
    )
    IssueExtras.objects.create(
        issue=issue,
        org_committee=data.get("org_committee") or [],
        files={},
        status="draft",
    )
    return issue


def list_candidate_submissions(issue_id: str) -> list[dict[str, Any]]:
    _get_issue_row(issue_id)
    service = SubmissionService()
    rows = Submission.objects.filter(issue_id=issue_id, status="accepted").order_by("created_at")
    return [service.get_submission(row.submission_id) for row in rows]


def list_included_submissions(issue_id: str) -> list[dict[str, Any]]:
    _get_issue_row(issue_id)
    service = SubmissionService()
    rows = Submission.objects.filter(
        issue_id=issue_id,
        status__in={"included_in_issue", "published"},
    ).order_by("created_at")
    return [service.get_submission(row.submission_id) for row in rows]


def add_submission(issue_id: str, submission_id: str, actor=None) -> dict[str, Any]:
    _get_issue_row(issue_id)
    try:
        submission = Submission.objects.get(pk=submission_id)
    except Submission.DoesNotExist as exc:
        raise KeyError(f"Заявка {submission_id!r} не найдена") from exc
    if submission.issue_id != issue_id:
        raise ValueError("Заявка относится к другому выпуску.")
    assert_transition(submission.status, "included_in_issue")
    changed_by = (actor.get_full_name() or actor.username) if actor else "editor"
    return SubmissionService().update_submission_status(
        submission_id,
        "included_in_issue",
        "Материал включён в выпуск.",
        changed_by,
        actor,
    )


def remove_submission(issue_id: str, submission_id: str, actor=None) -> dict[str, Any]:
    _get_issue_row(issue_id)
    try:
        submission = Submission.objects.get(pk=submission_id)
    except Submission.DoesNotExist as exc:
        raise KeyError(f"Заявка {submission_id!r} не найдена") from exc
    if submission.issue_id != issue_id:
        raise ValueError("Заявка относится к другому выпуску.")
    if submission.status == "published":
        raise ValueError("Опубликованный материал нельзя исключить без пересборки выпуска.")
    assert_transition(submission.status, "accepted")
    changed_by = (actor.get_full_name() or actor.username) if actor else "editor"
    return SubmissionService().update_submission_status(
        submission_id,
        "accepted",
        "Материал исключён из выпуска.",
        changed_by,
        actor,
    )


def _issue_row_to_dict(issue: Issue, candidates_count: int = 0, included_count: int = 0) -> dict[str, Any]:
    extras = _get_or_create_extras(issue)
    return {
        "issue_id": issue.issue_id,
        "conference_id": issue.conference_id,
        "conference_title": issue.conference.title,
        "conference_description": issue.conference.description,
        "title": issue.title,
        "year": issue.year,
        "quarter": issue.quarter,
        "status": extras.status,
        "published_at": extras.published_at.isoformat() if extras.published_at else None,
        "org_committee": extras.org_committee or [],
        "files": extras.files or {},
        "candidates_count": candidates_count,
        "included_count": included_count,
        "submissions_count": Submission.objects.filter(issue=issue).count(),
    }


def list_issues_summary() -> list[dict[str, Any]]:
    result = []
    for issue in Issue.objects.select_related("conference").order_by("-year", "-quarter"):
        candidates = Submission.objects.filter(issue=issue, status="accepted").count()
        included = Submission.objects.filter(issue=issue, status__in={"included_in_issue", "published"}).count()
        result.append(_issue_row_to_dict(issue, candidates, included))
    return result


def list_open_issues_summary() -> list[dict[str, Any]]:
    """Выпуски, в которые автору разрешено подать новый материал."""
    return [row for row in list_issues_summary() if row.get("status") != "published"]


def list_published_issues_summary() -> list[dict[str, Any]]:
    return [row for row in list_issues_summary() if row.get("status") == "published"]


def issue_to_dict(issue_id: str) -> dict[str, Any]:
    issue = _get_issue_row(issue_id)
    included = list_included_submissions(issue_id)
    sections = group_by_section(included)
    payload = _issue_row_to_dict(
        issue,
        candidates_count=len(list_candidate_submissions(issue_id)),
        included_count=len(included),
    )
    payload["sections"] = [
        {"title": section["title"], "submissions": [item["submission_id"] for item in section["submissions"]]}
        for section in sections
    ]
    payload["sections_detailed"] = sections
    return payload


def run_pdf_export(submission_id: str, actor=None) -> dict[str, Any]:
    service = SubmissionService()
    submission = service.get_submission(submission_id)
    formatted_reference = (submission.get("files") or {}).get("formatted_docx")
    if not formatted_reference:
        return {"status": "failed", "message": "Не найден formatted_material.docx для этой заявки."}
    submission_dir = resolve_stored_file_path(formatted_reference).parent
    report = finalize_submission_files(submission_dir)
    mapping = {
        "formatted_pdf": report.get("pdf_path"),
        "result_manifest": report.get("manifest_path"),
        "result_package": (report.get("zip") or {}).get("zip_path"),
    }
    for file_type, path in mapping.items():
        if path and Path(path).is_file():
            service.save_or_update_file_path(submission_id, file_type, path)
    service.add_event(submission_id, "pdf_export_finished", report, actor=actor)
    return report


def _prepare_for_builder(submission: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(submission)
    files = dict(prepared.get("files") or {})
    if files.get("formatted_pdf"):
        files["formatted_pdf"] = str(resolve_stored_file_path(files["formatted_pdf"]))
    prepared["files"] = files
    return prepared


@transaction.atomic
def build_issue_collection(issue_id: str) -> dict[str, Any]:
    issue = _get_issue_row(issue_id)
    extras = _get_or_create_extras(issue)
    included = list_included_submissions(issue_id)
    if not included:
        raise ValueError("В выпуске нет ни одного включённого материала — собирать нечего.")

    prepared = [_prepare_for_builder(row) for row in included]
    issue_dict = _issue_row_to_dict(issue)
    issue_dict["published_at"] = issue_dict.get("published_at") or date.today().isoformat()
    conference_dict = {"title": issue.conference.title, "description": issue.conference.description}
    issue_dir = get_issues_dir(issue_id)
    collection_result = build_collection_pdf(
        conference=conference_dict,
        issue=issue_dict,
        submissions=prepared,
        output_path=issue_dir / COLLECTION_FILENAME,
    )

    collection_link = (
        f"/issues/{issue_id}/download/collection/" if collection_result.status != "failed" else None
    )
    archive_html = build_archive_html(
        conference=conference_dict,
        issue=issue_dict,
        submissions=included,
        material_link_fn=lambda submission_id: f"/archive/materials/{submission_id}.pdf",
        collection_link=collection_link,
    )
    archive_path = save_archive_html(archive_html, issue_dir / ARCHIVE_FILENAME)

    files = dict(extras.files or {})
    if collection_result.output_path:
        files["collection_pdf"] = project_path_reference(collection_result.output_path)
    files["archive_page"] = project_path_reference(archive_path)
    extras.files = files
    extras.published_at = extras.published_at or date.today()
    if collection_result.status == "success":
        extras.status = "published"
    extras.save(update_fields=["files", "published_at", "status"])

    if collection_result.status == "success":
        service = SubmissionService()
        for submission_id in collection_result.included_submissions:
            model = Submission.objects.get(pk=submission_id)
            if model.status == "included_in_issue":
                service.update_submission_status(
                    submission_id,
                    "published",
                    f"Материал опубликован в выпуске {issue_id}.",
                    "issue_builder",
                )

    return {
        "status": collection_result.status,
        "collection": collection_result.to_dict(),
        "archive_page": project_path_reference(archive_path),
        "issue": issue_to_dict(issue_id),
    }
