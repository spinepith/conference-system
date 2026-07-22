from __future__ import annotations

import json
from pathlib import PurePosixPath

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from accounts.permissions import editor_required, is_editor
from submissions.models import Submission
from submissions.presentation import format_check
from submissions.services import SubmissionService, resolve_stored_file_path
from submissions.status_machine import VALID_STATUSES
from tema.issue_builder.archive_page import ensure_archive_sticky_footer

from . import services as issue_service

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
STATUS_LABELS = {
    "draft": "Черновик",
    "uploaded": "Материал загружен",
    "structure_extracted": "Структура извлечена",
    "formatted": "Материал оформлен",
    "auto_checking": "Автоматическая проверка",
    "auto_checked": "Проверки завершены",
    "needs_author_review": "Согласование автора",
    "author_confirmed": "Автор подтвердил",
    "needs_revision": "Требуется доработка",
    "editor_review": "На проверке редактора",
    "accepted": "Принято",
    "rejected": "Отклонено",
    "included_in_issue": "Включено в выпуск",
    "published": "Опубликовано",
    "error": "Ошибка обработки",
}
RISK_LABELS = {
    "low": "Низкий",
    "medium": "Средний",
    "high": "Высокий",
    "critical": "Критический",
}
DECISION_TO_STATUS = {
    "accept": "accepted",
    "reject": "rejected",
    "revision": "needs_revision",
    "return_to_author": "needs_author_review",
}

FILE_TYPE_PRESENTATION = {
    "original_docx": ("DOCX", "Исходный материал"),
    "revision_docx": ("DOCX", "Исправленная версия"),
    "formatted_docx": ("DOCX", "Оформленная версия"),
    "formatted_pdf": ("PDF", "PDF материала"),
    "author_report": ("PDF", "Отчёт для автора"),
    "check_report": ("JSON", "Отчёт автоматических проверок"),
    "extracted_metadata": ("JSON", "Извлечённые метаданные"),
    "formatting_report": ("JSON", "Отчёт об оформлении"),
    "result_manifest": ("JSON", "Состав итогового пакета"),
    "result_package": ("ZIP", "Итоговый пакет файлов"),
}
DECISION_LABELS = {
    "accept": "Материал принят.",
    "reject": "Материал отклонён.",
    "revision": "Материал отправлен на доработку.",
    # Retained for compatibility with old records/API clients. The button is
    # intentionally absent from the current UI because the editor does not
    # upload an edited version that would require a separate confirmation.
    "return_to_author": "Материал возвращён автору на согласование.",
    "include_in_issue": "Материал включён в выпуск.",
    "exclude_from_issue": "Материал исключён из выпуска.",
}


DOCX_FIELD_LABELS = {
    "title_ru": "Название материала",
    "title_en": "Название на английском языке",
    "authors": "Авторы",
    "organization": "Организация",
    "supervisor": "Научный руководитель",
    "abstract_ru": "Аннотация",
    "abstract_en": "Аннотация на английском языке",
    "keywords_ru": "Ключевые слова",
    "keywords_en": "Ключевые слова на английском языке",
    "body_text": "Основной текст",
    "references": "Список литературы",
}

DOCX_REPORT_STATUS_LABELS = {
    "success": "DOCX успешно приведён к шаблону",
    "partial": "DOCX оформлен с предупреждениями",
    "warning": "DOCX оформлен с предупреждениями",
    "failed": "Не удалось оформить DOCX",
}

DECISION_DISPLAY_LABELS = {
    "accept": "Принято",
    "reject": "Отклонено",
    "revision": "Отправлено на доработку",
    "return_to_author": "Возвращено автору на согласование",
    "include_in_issue": "Включено в выпуск",
    "exclude_from_issue": "Исключено из выпуска",
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
        decision["decision_label"] = DECISION_DISPLAY_LABELS.get(
            decision.get("decision"),
            decision.get("decision"),
        )
    return submission


def _with_file_cards(submission: dict) -> dict:
    cards = []
    for file_type, path in (submission.get("files") or {}).items():
        badge, label = FILE_TYPE_PRESENTATION.get(
            file_type,
            (PurePosixPath(str(path).replace("\\", "/")).suffix.lstrip(".").upper() or "FILE",
             "Файл результата"),
        )
        filename = PurePosixPath(str(path).replace("\\", "/")).name or file_type
        cards.append({
            "file_type": file_type,
            "badge": badge,
            "label": label,
            "filename": filename,
        })
    submission["file_cards"] = cards
    return submission


def _read_json_result(submission: dict, file_type: str) -> dict:
    stored_path = (submission.get("files") or {}).get(file_type)
    if not stored_path:
        return {}
    try:
        path = resolve_stored_file_path(stored_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _field_labels(values) -> list[str]:
    result: list[str] = []
    for value in values or []:
        key = str(value or "").strip()
        if not key:
            continue
        result.append(DOCX_FIELD_LABELS.get(key, key.replace("_", " ").capitalize()))
    return result


def _with_docx_summary(submission: dict) -> dict:
    metadata = _read_json_result(submission, "extracted_metadata")
    formatting = _read_json_result(submission, "formatting_report")

    # Fallback for older applications where the report file was not registered,
    # but the workflow result still contains the same JSON contract.
    if not formatting:
        for stage in submission.get("workflow_results") or []:
            if stage.get("stage_id") != "format_to_template":
                continue
            result = stage.get("result") or {}
            if isinstance(result, dict):
                formatting = result.get("report") if isinstance(result.get("report"), dict) else result
            break

    warnings: list[str] = []
    for source in (metadata.get("warnings", []), formatting.get("warnings", [])):
        for warning in source or []:
            text = str(warning or "").strip()
            if text and text not in warnings:
                warnings.append(text)

    objects = metadata.get("objects") if isinstance(metadata.get("objects"), dict) else {}
    authors = metadata.get("authors") if isinstance(metadata.get("authors"), list) else []
    filled_fields = _field_labels(formatting.get("filled_fields", []))
    missing_fields = _field_labels(formatting.get("missing_fields", []))
    raw_status = str(formatting.get("status") or "").strip()

    if not metadata and not formatting:
        submission["docx_summary"] = None
        return submission

    submission["docx_summary"] = {
        "title": str(metadata.get("title") or (submission.get("metadata") or {}).get("title_ru") or "").strip(),
        "organization": str(metadata.get("organization") or "").strip(),
        "authors_count": len(authors),
        "tables_count": int(objects.get("tables_count") or 0),
        "figures_count": int(objects.get("figures_count") or 0),
        "equations_count": int(objects.get("equations_count") or 0),
        "status": raw_status,
        "status_label": DOCX_REPORT_STATUS_LABELS.get(raw_status, "Данные DOCX извлечены"),
        "template_used": PurePosixPath(str(formatting.get("template_used") or "").replace("\\", "/")).name,
        "filled_fields": filled_fields,
        "missing_fields": missing_fields,
        "warnings": warnings,
    }
    return submission


def _with_summary(submission: dict) -> dict:
    checks = submission.get("checks") or []
    submission["overall_risk"] = (
        max((row.get("risk_level", "low") for row in checks), key=lambda value: RISK_ORDER.get(value, 0))
        if checks else None
    )
    submission["risk_label"] = RISK_LABELS.get(submission["overall_risk"], "Нет проверок")
    submission["status_label"] = STATUS_LABELS.get(submission.get("status"), submission.get("status"))

    display_checks = [format_check(check, audience="editor") for check in checks]
    for source, formatted in zip(checks, display_checks):
        source.update(formatted)
    return submission


@editor_required
def editor_list(request: HttpRequest):
    svc = _service()
    svc.ensure_defaults()
    issue_id = request.GET.get("issue_id", "").strip()
    status = request.GET.get("status", "").strip()
    risk = request.GET.get("risk", "").strip()
    query = request.GET.get("q", "").strip()

    base_rows = Submission.objects.select_related("owner").prefetch_related("authors", "files", "checks")
    editor_stats = {
        "total": base_rows.count(),
        "review": base_rows.filter(status="editor_review").count(),
        "revision": base_rows.filter(status="needs_revision").count(),
        "accepted": base_rows.filter(status__in={"accepted", "included_in_issue", "published"}).count(),
    }

    rows = base_rows.order_by("-updated_at")
    if issue_id:
        rows = rows.filter(issue_id=issue_id)
    if status:
        rows = rows.filter(status=status)
    submissions = [_with_display_times(_with_summary(svc.to_dict(row, compact=True))) for row in rows]
    if risk:
        submissions = [row for row in submissions if row.get("overall_risk") == risk]
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
        "editor_stats": editor_stats,
        "issues": issue_service.list_issues_summary(),
        "statuses": [(value, STATUS_LABELS.get(value, value)) for value in sorted(VALID_STATUSES)],
        "risks": [(value, label) for value, label in RISK_LABELS.items()],
        "filter_issue_id": issue_id,
        "filter_status": status,
        "filter_risk": risk,
        "filter_q": query,
    })


@editor_required
def editor_card(request: HttpRequest, submission_id: str):
    try:
        submission = _with_file_cards(
            _with_docx_summary(_with_display_times(_with_summary(_service().get_submission(submission_id))))
        )
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    return render(request, "editorial/editor_card.html", {"submission": submission})


@editor_required
@require_POST
def editor_decision(request: HttpRequest, submission_id: str):
    decision = request.POST.get("decision", "")
    comment = request.POST.get("comment", "").strip()
    svc = _service()
    try:
        submission = svc.get_submission_model(submission_id)
        if decision == "include_in_issue":
            if submission.status != "accepted":
                raise ValueError("Сначала примите материал, затем включите его в выпуск.")
            issue_service.add_submission(submission.issue_id, submission_id, actor=request.user)
        elif decision == "exclude_from_issue":
            if submission.status != "included_in_issue":
                raise ValueError("Исключить можно только материал, уже включённый в выпуск.")
            issue_service.remove_submission(submission.issue_id, submission_id, actor=request.user)
        else:
            if decision not in DECISION_TO_STATUS:
                raise ValueError("Неизвестное решение редактора.")
            svc.apply_editor_decision(
                submission_id,
                decision,
                request.user,
                comment or DECISION_LABELS[decision],
            )
        if decision in {"include_in_issue", "exclude_from_issue"}:
            svc.save_editor_decision(
                submission_id,
                decision,
                request.user,
                comment or DECISION_LABELS[decision],
            )
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
    html_content = ensure_archive_sticky_footer(path.read_text(encoding="utf-8"))
    return HttpResponse(html_content, content_type="text/html; charset=utf-8")
