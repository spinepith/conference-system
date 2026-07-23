from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from accounts.permissions import editor_required, is_editor
from .models import SubmissionExtras
from submissions.models import Submission
from submissions.services import SubmissionService, resolve_stored_file_path
from submissions.status_machine import VALID_STATUSES, ALLOWED_TRANSITIONS

from . import services as issue_service

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
DECISION_TO_STATUS = {
    "accept": "accepted",
    "reject": "rejected",
    "return_to_author": "needs_author_review",
}
DECISION_LABELS = {
    "accept": "Материал принят.",
    "reject": "Материал отклонён.",
    "return_to_author": "Материал отправлен на доработку.",
    "postpone": "Решение по материалу отложено.",
    "include_in_issue": "Материал включён в выпуск.",
    "exclude_from_issue": "Материал исключён из выпуска.",
}


def _service() -> SubmissionService:
    return SubmissionService()


def _display_datetime(value) -> str:
    if not value:
        return "—"
    parsed = parse_datetime(value) if isinstance(value, str) else value
    if parsed is None:
        return str(value)
    if timezone.is_aware(parsed):
        parsed = timezone.localtime(parsed)
    return parsed.strftime("%d.%m.%Y %H:%M:%S")


def _with_display_times(submission: dict) -> dict:
    submission["created_at_display"] = _display_datetime(submission.get("created_at"))
    submission["updated_at_display"] = _display_datetime(submission.get("updated_at"))
    for item in submission.get("status_history") or []:
        item["changed_at_display"] = _display_datetime(item.get("changed_at"))
    for item in submission.get("workflow_results") or []:
        item["started_at_display"] = _display_datetime(item.get("started_at"))
        item["finished_at_display"] = _display_datetime(item.get("finished_at"))
    for item in submission.get("events") or []:
        item["created_at_display"] = _display_datetime(item.get("created_at"))
    decision = submission.get("editor_decision")
    if decision:
        decision["created_at_display"] = _display_datetime(decision.get("created_at"))
    return submission


def _with_summary(submission: dict) -> dict:
    checks = submission.get("checks") or []
    submission["overall_risk"] = (
        max((row.get("risk_level", "low") for row in checks), key=lambda value: RISK_ORDER.get(value, 0))
        if checks else None
    )
    warnings: list[str] = []
    for check in checks:
        for item in check.get("warnings", []) or []:
            if isinstance(item, dict):
                text = item.get("message") or item.get("reason") or item.get("code")
            else:
                text = str(item)
            if text:
                warnings.append(str(text))
    submission["checks_summary"] = warnings[:5]
    return submission


@editor_required
def editor_list(request: HttpRequest):
    svc = _service()
    svc.ensure_defaults()
    issue_id = request.GET.get("issue_id", "").strip()
    status = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    rows = Submission.objects.select_related("owner").prefetch_related("authors", "files", "checks").order_by("-updated_at")
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


def _is_postponed_for_status(submission_id: str, status: str) -> bool:
    extras = SubmissionExtras.objects.filter(pk=submission_id).first()
    return bool(extras and extras.postponed_at and extras.postponed_at_status == status)


@editor_required
def editor_card(request: HttpRequest, submission_id: str):
    try:
        submission = _with_display_times(_with_summary(_service().get_submission(submission_id)))
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    postponed = _is_postponed_for_status(submission_id, submission["status"])
    available_issues = issue_service.list_issues_summary()
    return render(request, "editorial/editor_card.html", {
        "submission": submission,
        "available_decisions": _available_decisions(submission["status"], postponed),
        "available_issues": available_issues,
    })


@editor_required
@require_POST
@editor_required
@require_POST
def editor_decision(request: HttpRequest, submission_id: str):
    decision = request.POST.get("decision", "")
    comment = request.POST.get("comment", "").strip()
    target_issue = request.POST.get("target_issue", "").strip()
    svc = _service()
    try:
        submission = svc.get_submission_model(submission_id)
        postponed = _is_postponed_for_status(submission_id, submission.status)
        available = _available_decisions(submission.status, postponed)
        if not available.get(decision):
            raise ValueError(
                f"Действие «{DECISION_LABELS.get(decision, decision)}» недоступно "
                f"для текущего статуса заявки «{submission.status}»."
            )
        if decision == "postpone":
            svc.save_editor_decision(
                submission_id,
                "postpone",
                request.user,
                comment or DECISION_LABELS["postpone"],
            )
            SubmissionExtras.objects.update_or_create(
                submission_id=submission_id,
                defaults={"postponed_at": timezone.now(), "postponed_at_status": submission.status},
            )
        elif decision == "include_in_issue":
            issue_id = target_issue if target_issue else submission.issue_id
            issue_service.add_submission(issue_id, submission_id, actor=request.user)
            svc.save_editor_decision(submission_id, decision, request.user, comment or DECISION_LABELS[decision])
        elif decision == "exclude_from_issue":
            issue_service.remove_submission(submission.issue_id, submission_id, actor=request.user)
            svc.save_editor_decision(submission_id, decision, request.user, comment or DECISION_LABELS[decision])
        else:
            if decision not in DECISION_TO_STATUS:
                raise ValueError("Неизвестное решение редактора.")
            svc.apply_editor_decision(
                submission_id,
                decision,
                request.user,
                comment or DECISION_LABELS[decision],
            )
        if decision != "postpone":
            SubmissionExtras.objects.filter(pk=submission_id).delete()
        messages.success(request, DECISION_LABELS.get(decision, "Решение сохранено."))
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:editor_card", submission_id=submission_id)


@editor_required
@require_POST
def run_pdf_export(request: HttpRequest, submission_id: str):
    result = issue_service.run_pdf_export(submission_id, actor=request.user)
    if result.get("status") == "failed":
        messages.error(request, result.get("message", "Не удалось сформировать PDF."))
    elif result.get("status") == "warning":
        messages.warning(request, result.get("message", "PDF создан с предупреждениями."))
    else:
        messages.success(request, result.get("message", "PDF и ZIP сформированы."))
    return redirect("editorial:editor_card", submission_id=submission_id)


@editor_required
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


@editor_required
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


@editor_required
def issue_detail(request: HttpRequest, issue_id: str):
    try:
        issue = issue_service.issue_to_dict(issue_id)
    except KeyError as exc:
        raise Http404(str(exc)) from exc
    return render(request, "editorial/issue_detail.html", {
        "issue": issue,
        "candidates": issue_service.list_candidate_submissions(issue_id),
    })


@editor_required
@require_POST
def issue_add_submission(request: HttpRequest, issue_id: str, submission_id: str):
    try:
        issue_service.add_submission(issue_id, submission_id, actor=request.user)
        messages.success(request, "Материал добавлен в выпуск.")
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:issue_detail", issue_id=issue_id)


@editor_required
@require_POST
def issue_remove_submission(request: HttpRequest, issue_id: str, submission_id: str):
    try:
        issue_service.remove_submission(issue_id, submission_id, actor=request.user)
        messages.success(request, "Материал исключён из выпуска.")
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:issue_detail", issue_id=issue_id)


@editor_required
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


@editor_required
@require_POST
def issue_delete(request: HttpRequest, issue_id: str):
    try:
        issue_service.delete_issue(issue_id)
        messages.success(request, f"Выпуск {issue_id} удалён из архива.")
    except (KeyError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("editorial:issue_list")


def _visible_issue_or_404(request: HttpRequest, issue_id: str) -> dict:
    try:
        issue = issue_service.issue_to_dict(issue_id)
    except KeyError as exc:
        raise Http404(str(exc)) from exc
    if issue.get("status") != "published" and not is_editor(request.user):
        raise Http404("Выпуск не опубликован.")
    return issue


def download_collection(request: HttpRequest, issue_id: str):
    issue = _visible_issue_or_404(request, issue_id)
    reference = (issue.get("files") or {}).get("collection_pdf")
    if not reference:
        raise Http404("Сборник ещё не сформирован.")
    path = resolve_stored_file_path(reference)
    if not path.is_file():
        raise Http404("Файл сборника отсутствует.")
    return FileResponse(path.open("rb"), as_attachment=True, filename=f"{issue_id}_collection.pdf")


def public_material_pdf(request: HttpRequest, submission_id: str):
    try:
        submission = Submission.objects.prefetch_related("files").get(pk=submission_id, status="published")
    except Submission.DoesNotExist as exc:
        raise Http404("Материал не опубликован.") from exc
    reference = SubmissionService._latest_files(submission).get("formatted_pdf")
    if not reference:
        raise Http404("PDF материала отсутствует.")
    path = resolve_stored_file_path(reference)
    if not path.is_file():
        raise Http404("PDF материала отсутствует в хранилище.")
    return FileResponse(path.open("rb"), as_attachment=True, filename=f"{submission_id}.pdf")


def archive_index(request: HttpRequest):
    return render(
        request,
        "editorial/archive_index.html",
        {"issues": issue_service.list_published_issues_summary()},
    )


def archive_issue(request: HttpRequest, issue_id: str):
    issue = _visible_issue_or_404(request, issue_id)
    reference = (issue.get("files") or {}).get("archive_page")
    if not reference:
        raise Http404("Страница архива ещё не сформирована.")
    path = resolve_stored_file_path(reference)
    if not path.is_file():
        raise Http404("Страница архива отсутствует.")
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


def _last_transition_is_author_confirmation(history_entries) -> bool:
    entries = list(history_entries)
    if not entries:
        return False
    last = entries[-1]
    from_status = last.from_status if hasattr(last, "from_status") else last.get("from_status")
    to_status = last.to_status if hasattr(last, "to_status") else last.get("to_status")
    return from_status == "author_confirmed" and to_status == "editor_review"


def _available_decisions(status: str, postponed: bool = False) -> dict[str, bool]:
    allowed_next = ALLOWED_TRANSITIONS.get(status, set())
    accept = "accepted" in allowed_next
    reject = "rejected" in allowed_next
    return_to_author = "needs_author_review" in allowed_next
    include_in_issue = status == "accepted"
    exclude_from_issue = status == "included_in_issue"
    return {
        "accept": accept,
        "reject": reject,
        "return_to_author": return_to_author,
        "include_in_issue": include_in_issue,
        "exclude_from_issue": exclude_from_issue,
        "postpone": any([accept, reject, return_to_author, include_in_issue, exclude_from_issue]) and not postponed,
    }