from __future__ import annotations

import json
import secrets
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpRequest, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.permissions import can_view_submission, editor_required, is_editor

from .forms import SubmissionForm
from .models import Submission, SubmissionFile
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


def index(request: HttpRequest):
    submissions = []
    if request.user.is_authenticated:
        submissions = service().list_submissions(
            owner=request.user,
            audience="author",
        )
        for row in submissions:
            row["status_label"] = STATUS_LABELS.get(row["status"], row["status"])
    return render(request, "index.html", {"submissions": submissions})


@login_required
@require_http_methods(["GET", "POST"])
def submit_material(request: HttpRequest):
    if is_editor(request.user):
        messages.error(request, "Редактор и администратор не могут подавать материалы.")
        return redirect("index")
    svc = service()
    svc.ensure_defaults()
    initial = {
        "full_name": _display_name(request.user),
        "email": request.user.email,
    }
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = svc.create_submission_from_form(
                form.cleaned_data,
                form.cleaned_data["docx_file"],
                owner=request.user,
            )
            return redirect("status", submission_id=submission["submission_id"])
    else:
        form = SubmissionForm(initial=initial)
    return render(request, "submit.html", {"form": form})


@login_required
def status_page(request: HttpRequest, submission_id: str):
    submission = _visible_submission_or_404(request, submission_id)
    author_files = submission.files.filter(file_type__in=AUTHOR_VISIBLE_FILE_TYPES)
    return render(
        request,
        "status.html",
        {
            "submission": submission,
            "author_files": author_files,
            "status_label": STATUS_LABELS.get(submission.status, submission.status),
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


@login_required
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


@login_required
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
