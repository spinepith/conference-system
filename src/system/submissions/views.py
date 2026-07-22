from __future__ import annotations

import json
import secrets
from functools import wraps
from pathlib import PurePosixPath

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.permissions import (
    author_required,
    can_view_submission,
    editor_required,
    is_administrator,
    is_author,
    is_editor,
)

from .forms import SubmissionForm
from .models import Submission, SubmissionFile
from .presentation import format_check
from .services import SubmissionService, resolve_stored_file_path
from .workflow import WorkflowEngine


AUTHOR_VISIBLE_FILE_TYPES = {
    "original_docx",
    "revision_docx",
    "formatted_docx",
    "formatted_pdf",
    "result_package",
}

STATUS_LABELS = {
    "draft": "Черновик",
    "uploaded": "Материал загружен",
    "structure_extracted": "Структура извлечена",
    "formatted": "Материал оформлен",
    "auto_checking": "Выполняются автоматические проверки",
    "auto_checked": "Автоматические проверки завершены",
    "needs_author_review": "Требуется согласование автора",
    "author_confirmed": "Итоговый вариант подтверждён",
    "needs_revision": "Требуется доработка",
    "editor_review": "Материал проверяется редактором",
    "accepted": "Материал принят",
    "rejected": "Материал отклонён",
    "included_in_issue": "Материал включён в выпуск",
    "published": "Материал опубликован",
    "error": "Ошибка обработки",
}

STATUS_PROGRESS = {
    "draft": 5,
    "uploaded": 15,
    "structure_extracted": 30,
    "formatted": 45,
    "auto_checking": 55,
    "auto_checked": 65,
    "needs_author_review": 70,
    "needs_revision": 58,
    "author_confirmed": 77,
    "editor_review": 82,
    "accepted": 90,
    "rejected": 100,
    "included_in_issue": 95,
    "published": 100,
    "error": 45,
}

STATUS_STEP = {
    "draft": 1,
    "uploaded": 1,
    "structure_extracted": 2,
    "formatted": 2,
    "auto_checking": 3,
    "auto_checked": 3,
    "needs_author_review": 4,
    "needs_revision": 4,
    "author_confirmed": 4,
    "editor_review": 5,
    "accepted": 5,
    "rejected": 5,
    "included_in_issue": 6,
    "published": 6,
    "error": 3,
}

STATUS_TONE = {
    "accepted": "success",
    "included_in_issue": "success",
    "published": "success",
    "needs_author_review": "warning",
    "needs_revision": "warning",
    "rejected": "danger",
    "error": "danger",
    "draft": "neutral",
}

WORKFLOW_LABELS = [
    "Загрузка",
    "Оформление",
    "Проверка",
    "Согласование",
    "Редактор",
    "Публикация",
]

FILE_TYPE_LABELS = {
    "original_docx": ("Исходный материал", "DOCX"),
    "revision_docx": ("Исправленная версия", "DOCX"),
    "formatted_docx": ("Оформленная версия", "DOCX"),
    "formatted_pdf": ("Версия для просмотра", "PDF"),
    "result_package": ("Пакет результатов", "ZIP"),
}


def _decorate_submission_row(row: dict) -> dict:
    status = row.get("status", "draft")
    row["status_label"] = STATUS_LABELS.get(status, status)
    row["status_tone"] = STATUS_TONE.get(status, "info")
    row["progress_percent"] = STATUS_PROGRESS.get(status, 0)
    return row


def _workflow_steps(status: str) -> list[dict[str, str]]:
    current_step = STATUS_STEP.get(status, 1)
    steps = []
    for index, label in enumerate(WORKFLOW_LABELS, start=1):
        state = "future"
        if index < current_step:
            state = "complete"
        elif index == current_step:
            state = "current"
        steps.append({"number": str(index), "label": label, "state": state})
    return steps


def service() -> SubmissionService:
    return SubmissionService()


def parse_json_request(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Некорректный JSON") from exc


def _display_name(user) -> str:
    return user.get_full_name() or user.username


def _owned_submission_or_404(request: HttpRequest, submission_id: str) -> Submission:
    return get_object_or_404(
        Submission.objects.select_related("owner"),
        pk=submission_id,
        owner=request.user,
    )


def _visible_submission_or_404(request: HttpRequest, submission_id: str) -> Submission:
    submission = get_object_or_404(
        Submission.objects.select_related("owner").prefetch_related(
            "authors",
            "files",
            "checks",
            "status_history",
        ),
        pk=submission_id,
    )
    if not can_view_submission(request.user, submission):
        raise Http404("Заявка не найдена")
    return submission


def internal_api_required(view_func):
    @wraps(view_func)
    def wrapped(request: HttpRequest, *args, **kwargs):
        expected = settings.INTERNAL_API_TOKEN
        supplied = request.headers.get("X-Internal-Token", "")
        if not expected or not secrets.compare_digest(supplied, expected):
            return JsonResponse(
                {"error": "Недействительный внутренний API-токен."},
                status=403,
                json_dumps_params={"ensure_ascii": False},
            )
        return view_func(request, *args, **kwargs)

    return wrapped


def _public_site_context() -> dict:
    from tema.editorial import services as issue_service

    service().ensure_defaults()
    all_issues = issue_service.list_issues_summary()
    open_issues = issue_service.list_open_issues_summary()
    published_issues = issue_service.list_published_issues_summary()
    latest_issue = open_issues[0] if open_issues else (all_issues[0] if all_issues else None)
    return {
        "open_issues": open_issues,
        "latest_issue": latest_issue,
        "published_issues": published_issues[:3],
        "all_published_issues": published_issues,
        "platform_stats": {
            "published_materials": Submission.objects.filter(status="published").count(),
            "published_issues": len(published_issues),
        },
    }


def index(request: HttpRequest):
    """Public landing page. It remains public for every authenticated role."""
    return render(request, "index.html", _public_site_context())


def conferences_page(request: HttpRequest):
    """Public catalogue of conferences and their current/published issues."""
    return render(request, "conferences.html", _public_site_context())


@login_required
def cabinet_home(request: HttpRequest):
    """Send each account to its private workspace without hiding the public site."""
    if is_author(request.user):
        return redirect("author_dashboard")
    if is_editor(request.user):
        return redirect("editorial:editor_list")
    if is_administrator(request.user):
        return redirect("admin_dashboard")
    messages.warning(request, "Для аккаунта не назначена роль. Обратитесь к администратору.")
    return redirect("index")


@author_required
def author_dashboard(request: HttpRequest):
    submissions = service().list_submissions(owner=request.user, audience="author")
    submissions = [_decorate_submission_row(row) for row in submissions]
    author_stats = {
        "total": len(submissions),
        "active": sum(
            row["status"] not in {"published", "rejected", "accepted", "included_in_issue"}
            for row in submissions
        ),
        "attention": sum(
            row["status"] in {"needs_author_review", "needs_revision", "error"}
            for row in submissions
        ),
        "published": sum(row["status"] == "published" for row in submissions),
    }
    return render(
        request,
        "author_dashboard.html",
        {"submissions": submissions, "author_stats": author_stats},
    )


@login_required
def admin_dashboard(request: HttpRequest):
    if not is_administrator(request.user):
        raise PermissionDenied("Доступ разрешён только администратору.")

    from tema.editorial import services as issue_service

    return render(
        request,
        "admin_dashboard.html",
        {
            "platform_stats": {
                "users": get_user_model().objects.count(),
                "submissions": Submission.objects.count(),
                "conferences": issue_service.Conference.objects.count(),
                "issues": len(issue_service.list_issues_summary()),
            }
        },
    )


@author_required
@require_http_methods(["GET", "POST"])
def submit_material(request: HttpRequest):
    from tema.editorial import services as issue_service

    svc = service()
    svc.ensure_defaults()
    open_issues = issue_service.list_open_issues_summary()
    issue_choices = [
        (row["issue_id"], f'{row["conference_title"]} — {row["title"]} ({row["year"]}, Q{row["quarter"]})')
        for row in open_issues
    ]
    requested_issue = request.GET.get("issue", "")
    initial = {
        "full_name": _display_name(request.user),
        "email": request.user.email,
        "issue_id": requested_issue if requested_issue in {value for value, _ in issue_choices} else (issue_choices[0][0] if issue_choices else ""),
    }
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES, issue_choices=issue_choices)
        if form.is_valid():
            submission = svc.create_submission_from_form(
                form.cleaned_data,
                form.cleaned_data["docx_file"],
                owner=request.user,
            )
            return redirect("status", submission_id=submission["submission_id"])
    else:
        form = SubmissionForm(initial=initial, issue_choices=issue_choices)
    return render(
        request,
        "submit.html",
        {"form": form, "open_issues": open_issues, "has_open_issues": bool(issue_choices)},
    )


@author_required
def status_page(request: HttpRequest, submission_id: str):
    submission = _visible_submission_or_404(request, submission_id)
    author_files = submission.files.filter(file_type__in=AUTHOR_VISIBLE_FILE_TYPES)
    file_cards = []
    for file_row in author_files:
        label, extension = FILE_TYPE_LABELS.get(
            file_row.file_type,
            (file_row.file_type.replace("_", " ").title(), "FILE"),
        )
        filename = PurePosixPath(str(file_row.path).replace("\\", "/")).name or file_row.file_type
        file_cards.append(
            {
                "file": file_row,
                "label": label,
                "extension": extension,
                "filename": filename,
            }
        )

    revision_feedback = []
    last_revision_decision = None
    if submission.status == "needs_revision":
        revision_feedback = [
            formatted
            for formatted in (
                format_check(check, audience="author")
                for check in submission.checks.all()
            )
            if formatted["has_attention"]
        ]
        last_revision_decision = submission.editor_decisions.filter(decision="revision").first()

    return render(
        request,
        "status.html",
        {
            "submission": submission,
            "author_files": author_files,
            "file_cards": file_cards,
            "status_label": STATUS_LABELS.get(submission.status, submission.status),
            "status_tone": STATUS_TONE.get(submission.status, "info"),
            "progress_percent": STATUS_PROGRESS.get(submission.status, 0),
            "workflow_fill_percent": round(STATUS_PROGRESS.get(submission.status, 0) * 0.84, 1),
            "workflow_steps": _workflow_steps(submission.status),
            "action_required": submission.status in {"needs_author_review", "needs_revision", "error"},
            "can_upload_revision": submission.owner_id == request.user.id
            and submission.status in {"needs_author_review", "needs_revision", "error"},
            "revision_feedback": revision_feedback,
            "last_revision_decision": last_revision_decision,
        },
    )


@editor_required
@require_POST
def run_workflow_page(request: HttpRequest, submission_id: str):
    try:
        results = WorkflowEngine().run(submission_id)
        failed = [item for item in results if item.get("status") == "failed"]
        if failed:
            messages.error(request, "Обработка завершилась с ошибками. Проверьте результаты workflow.")
        else:
            messages.success(request, "Автоматическая обработка материала завершена.")
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    except Exception as exc:
        messages.error(request, f"Не удалось запустить обработку: {exc}")
    return redirect("editorial:editor_card", submission_id=submission_id)


@author_required
@require_POST
def confirm_submission(request: HttpRequest, submission_id: str):
    submission = _owned_submission_or_404(request, submission_id)
    svc = service()
    try:
        svc.update_submission_status(
            submission.submission_id,
            "author_confirmed",
            "Автор подтвердил итоговый вариант.",
            _display_name(request.user),
            request.user,
        )
        svc.update_submission_status(
            submission.submission_id,
            "editor_review",
            "Материал передан редактору.",
            "system",
        )
        messages.success(request, "Итоговый вариант подтверждён и передан редактору.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("status", submission_id=submission_id)


@author_required
@require_POST
def upload_revision(request: HttpRequest, submission_id: str):
    uploaded_file = request.FILES.get("revision_docx")
    if not uploaded_file or not uploaded_file.name.lower().endswith(".docx"):
        return HttpResponseBadRequest("Можно загрузить только DOCX-файл.")
    submission = _owned_submission_or_404(request, submission_id)
    if submission.status not in {"needs_revision", "needs_author_review", "error"}:
        messages.error(request, "Исправленную версию нельзя загрузить на текущем этапе.")
        return redirect("status", submission_id=submission_id)
    svc = service()
    svc.save_uploaded_file(submission, "revision_docx", uploaded_file, actor=request.user)
    try:
        svc.update_submission_status(
            submission_id,
            "uploaded",
            "Автор загрузил исправленную версию.",
            _display_name(request.user),
            request.user,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("status", submission_id=submission_id)
    messages.success(request, "Исправленная версия загружена.")
    return redirect("status", submission_id=submission_id)


@login_required
def download_file(request: HttpRequest, file_id: int):
    file_row = get_object_or_404(
        SubmissionFile.objects.select_related("submission__owner"),
        pk=file_id,
    )
    if not can_view_submission(request.user, file_row.submission):
        raise Http404("Файл не найден")
    if file_row.file_type not in AUTHOR_VISIBLE_FILE_TYPES:
        raise Http404("Служебный файл недоступен для скачивания.")
    path = resolve_stored_file_path(file_row.path)
    if not path.exists():
        raise Http404("Файл отсутствует в хранилище")
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)


@editor_required
def api_index(request: HttpRequest):
    return JsonResponse(
        {
            "service": "conference-system-django-core",
            "user_api": [
                "GET|POST /api/submissions/",
                "GET /api/submissions/<submission_id>/",
            ],
            "editor_api": [
                "POST /api/submissions/<submission_id>/editor-decision/",
            ],
            "internal_api": [
                "PATCH /api/submissions/<submission_id>/status/",
                "POST /api/submissions/<submission_id>/checks/",
                "POST /api/submissions/<submission_id>/events/",
                "POST /api/submissions/<submission_id>/files/",
                "POST /api/submissions/<submission_id>/workflow/run/",
            ],
        },
        json_dumps_params={"ensure_ascii": False},
    )


def api_health(request: HttpRequest):
    return JsonResponse({"status": "ok", "service": "conference-system-django-core"})


@login_required
def api_organizations(request: HttpRequest):
    q = request.GET.get("q")
    try:
        limit = int(request.GET.get("limit", "50"))
    except ValueError:
        limit = 50
    data = service().list_organizations(q=q, limit=limit)
    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})


@login_required
@require_http_methods(["GET", "POST"])
def api_submissions(request: HttpRequest):
    svc = service()
    if request.method == "GET":
        if is_editor(request.user):
            data = svc.list_submissions(issue_id=request.GET.get("issue_id"))
        else:
            data = svc.list_submissions(
                issue_id=request.GET.get("issue_id"),
                owner=request.user,
                audience="author",
            )
        return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})
    try:
        payload = parse_json_request(request)
        data = svc.create_submission(payload, owner=request.user)
        return JsonResponse(
            svc.to_author_dict(svc.get_submission_model(data["submission_id"])),
            status=201,
            json_dumps_params={"ensure_ascii": False},
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@login_required
def api_submission_detail(request: HttpRequest, submission_id: str):
    submission = _visible_submission_or_404(request, submission_id)
    svc = service()
    data = svc.to_dict(submission) if is_editor(request.user) else svc.to_author_dict(submission)
    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@internal_api_required
@require_http_methods(["PATCH", "POST"])
def api_submission_status(request: HttpRequest, submission_id: str):
    try:
        payload = parse_json_request(request)
        data = service().update_submission_status(
            submission_id,
            payload.get("status", ""),
            payload.get("comment", ""),
            "internal_service",
        )
        return JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@internal_api_required
@require_POST
def api_submission_checks(request: HttpRequest, submission_id: str):
    try:
        payload = parse_json_request(request)
        service().save_check_result(submission_id, payload)
        return JsonResponse({"status": "saved"}, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@internal_api_required
@require_POST
def api_submission_events(request: HttpRequest, submission_id: str):
    try:
        payload = parse_json_request(request)
        service().add_event(submission_id, payload.get("event_type", "event"), payload.get("payload", {}))
        return JsonResponse({"status": "saved"}, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@internal_api_required
@require_POST
def api_submission_files(request: HttpRequest, submission_id: str):
    svc = service()
    try:
        submission = svc.get_submission_model(submission_id)
        uploaded_file = request.FILES.get("file")
        file_type = request.POST.get("file_type", "file")
        if uploaded_file:
            if file_type in {"original_docx", "revision_docx"} and not uploaded_file.name.lower().endswith(".docx"):
                return JsonResponse({"error": "Можно загрузить только DOCX-файл."}, status=400, json_dumps_params={"ensure_ascii": False})
            row = svc.save_uploaded_file(submission, file_type, uploaded_file)
            return JsonResponse({"id": row.id, "file_type": row.file_type, "path": row.path}, json_dumps_params={"ensure_ascii": False})
        payload = parse_json_request(request)
        row = svc.save_file_path(submission_id, payload.get("file_type", "file"), payload.get("path", ""))
        return JsonResponse(row, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@editor_required
@require_POST
def api_editor_decision(request: HttpRequest, submission_id: str):
    try:
        payload = parse_json_request(request)
        row = service().apply_editor_decision(
            submission_id,
            payload.get("decision", ""),
            request.user,
            payload.get("comment", ""),
        )
        return JsonResponse(row, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@internal_api_required
@require_POST
def api_workflow_run(request: HttpRequest, submission_id: str):
    try:
        results = WorkflowEngine().run(submission_id)
        return JsonResponse({"status": "completed", "results": results}, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})
