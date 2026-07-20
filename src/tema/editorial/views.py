from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from submissions.models import Submission
from submissions.services import SubmissionService, resolve_stored_file_path
from submissions.status_machine import VALID_STATUSES

from . import services as issue_service

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
DECISION_TO_STATUS = {
    "accept": "accepted",
    "reject": "rejected",
    "revision": "needs_revision",
    "return_to_author": "needs_author_review",
}
DECISION_LABELS = {
    "accept": "Материал принят.",
    "reject": "Материал отклонён.",
    "revision": "Материал отправлен на доработку.",
    "return_to_author": "Материал возвращён автору на согласование.",
    "include_in_issue": "Материал включён в выпуск.",
    "exclude_from_issue": "Материал исключён из выпуска.",
}


def _service() -> SubmissionService:
    return SubmissionService()


def _with_summary(submission: dict) -> dict:
    checks = submission.get("checks") or []
    submission["overall_risk"] = (
        max((row.get("risk_level", "low") for row in checks), key=lambda value: RISK_ORDER.get(value, 0))
        if checks else None
    )
    warnings = []
    for check in checks:
        warnings.extend(str(item) for item in check.get("warnings", []) if item)
    submission["checks_summary"] = warnings[:5]
    return submission


def editor_list(request: HttpRequest):
    svc = _service()
    svc.ensure_defaults()
    issue_id = request.GET.get("issue_id", "").strip()
    status = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    rows = Submission.objects.prefetch_related("files", "checks").order_by("-updated_at")
    if issue_id:
        rows = rows.filter(issue_id=issue_id)
    if status:
        rows = rows.filter(status=status)
    submissions = [_with_summary(svc.to_dict(row, compact=True)) for row in rows]
    if query:
        needle = query.casefold()
        submissions = [
            row for row in submissions
            if needle in ((row.get("metadata") or {}).get("title_ru") or "").casefold()
            or needle in ((row.get("author_contact") or {}).get("full_name") or "").casefold()
            or any(needle in (author.get("full_name") or "").casefold() for author in row.get("authors", []))
        ]
    return render(request, "editorial/editor_list.html", {
        "submissions": submissions,
        "issues": issue_service.list_issues_summary(),
        "statuses": sorted(VALID_STATUSES),
        "filter_issue_id": issue_id,
        "filter_status": status,
        "filter_q": query,
    })


def editor_card(request: HttpRequest, submission_id: str):
    try:
        submission = _with_summary(_service().get_submission(submission_id))
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    return render(request, "editorial/editor_card.html", {"submission": submission})


@require_POST
def editor_decision(request: HttpRequest, submission_id: str):
    decision = request.POST.get("decision", "")
    comment = request.POST.get("comment", "").strip()
    editor_name = request.POST.get("editor_name", "").strip() or "editor"
    svc = _service()
    try:
        submission = svc.get_submission_model(submission_id)
        if decision == "include_in_issue":
            issue_service.add_submission(submission.issue_id, submission_id)
        elif decision == "exclude_from_issue":
            issue_service.remove_submission(submission.issue_id, submission_id)
        else:
            target = DECISION_TO_STATUS.get(decision)
            if not target:
                raise ValueError("Неизвестное решение редактора.")
            svc.update_submission_status(
                submission_id,
                target,
                comment or DECISION_LABELS[decision],
                editor_name,
            )
        svc.save_editor_decision(submission_id, decision, editor_name, comment)
        messages.success(request, DECISION_LABELS.get(decision, "Решение сохранено."))
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:editor_card", submission_id=submission_id)


@require_POST
def run_pdf_export(request: HttpRequest, submission_id: str):
    result = issue_service.run_pdf_export(submission_id)
    if result.get("status") == "failed":
        messages.error(request, result.get("message", "Не удалось сформировать PDF."))
    elif result.get("status") == "warning":
        messages.warning(request, result.get("message", "PDF создан с предупреждениями."))
    else:
        messages.success(request, result.get("message", "PDF и ZIP сформированы."))
    return redirect("editorial:editor_card", submission_id=submission_id)


def download_by_type(request: HttpRequest, submission_id: str, file_type: str):
    try:
        submission = _service().get_submission(submission_id)
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    reference = (submission.get("files") or {}).get(file_type)
    if not reference:
        raise Http404("Файл не найден для этой заявки.")
    path = resolve_stored_file_path(reference)
    if not path.is_file():
        raise Http404("Файл отсутствует в хранилище.")
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)


def issue_list(request: HttpRequest):
    if request.method == "POST":
        committee = [line.strip() for line in request.POST.get("org_committee", "").splitlines() if line.strip()]
        try:
            issue_service.create_issue({
                "issue_id": request.POST["issue_id"],
                "conference_id": request.POST.get("conference_id"),
                "title": request.POST["title"],
                "year": request.POST["year"],
                "quarter": request.POST["quarter"],
                "org_committee": committee,
            })
            messages.success(request, "Выпуск создан.")
            return redirect("editorial:issue_list")
        except (ValueError, KeyError) as exc:
            messages.error(request, str(exc))
    return render(request, "editorial/issue_list.html", {"issues": issue_service.list_issues_summary()})


def issue_detail(request: HttpRequest, issue_id: str):
    try:
        issue = issue_service.issue_to_dict(issue_id)
    except KeyError as exc:
        raise Http404(str(exc)) from exc
    return render(request, "editorial/issue_detail.html", {
        "issue": issue,
        "candidates": issue_service.list_candidate_submissions(issue_id),
    })


@require_POST
def issue_add_submission(request: HttpRequest, issue_id: str, submission_id: str):
    try:
        issue_service.add_submission(issue_id, submission_id)
        messages.success(request, "Материал добавлен в выпуск.")
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:issue_detail", issue_id=issue_id)


@require_POST
def issue_remove_submission(request: HttpRequest, issue_id: str, submission_id: str):
    try:
        issue_service.remove_submission(issue_id, submission_id)
        messages.success(request, "Материал исключён из выпуска.")
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:issue_detail", issue_id=issue_id)


@require_POST
def issue_build(request: HttpRequest, issue_id: str):
    try:
        result = issue_service.build_issue_collection(issue_id)
        if result["status"] == "failed":
            messages.error(request, result["collection"].get("error") or "Сборник не сформирован.")
        elif result["status"] == "partial":
            messages.warning(request, "Сборник сформирован частично: некоторые материалы пропущены.")
        else:
            messages.success(request, "PDF-сборник и страница архива сформированы.")
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:issue_detail", issue_id=issue_id)


def download_collection(request: HttpRequest, issue_id: str):
    try:
        reference = (issue_service.issue_to_dict(issue_id).get("files") or {}).get("collection_pdf")
    except KeyError as exc:
        raise Http404(str(exc)) from exc
    if not reference:
        raise Http404("Сборник ещё не сформирован.")
    path = resolve_stored_file_path(reference)
    if not path.is_file():
        raise Http404("Файл сборника отсутствует.")
    return FileResponse(path.open("rb"), as_attachment=True, filename=f"{issue_id}_collection.pdf")


def archive_index(request: HttpRequest):
    return render(request, "editorial/archive_index.html", {"issues": issue_service.list_issues_summary()})


def archive_issue(request: HttpRequest, issue_id: str):
    try:
        reference = (issue_service.issue_to_dict(issue_id).get("files") or {}).get("archive_page")
    except KeyError as exc:
        raise Http404(str(exc)) from exc
    if not reference:
        raise Http404("Страница архива ещё не сформирована.")
    path = resolve_stored_file_path(reference)
    if not path.is_file():
        raise Http404("Страница архива отсутствует.")
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")
