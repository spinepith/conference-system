from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpRequest, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import SubmissionForm
from .models import SubmissionFile
from .services import SubmissionService, resolve_stored_file_path
from .workflow import WorkflowEngine


AUTHOR_VISIBLE_FILE_TYPES = {
    "original_docx",
    "revision_docx",
    "formatted_docx",
    "formatted_pdf",
    "result_package",
}


def service() -> SubmissionService:
    return SubmissionService()


def parse_json_request(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Некорректный JSON")


def index(request: HttpRequest):
    svc = service()
    submissions = svc.list_submissions()
    return render(request, "index.html", {"submissions": submissions})


@require_http_methods(["GET", "POST"])
def submit_material(request: HttpRequest):
    svc = service()
    svc.ensure_defaults()
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = svc.create_submission_from_form(form.cleaned_data, form.cleaned_data["docx_file"])
            return redirect("status", submission_id=submission["submission_id"])
    else:
        form = SubmissionForm()
    return render(request, "submit.html", {"form": form})


def status_page(request: HttpRequest, submission_id: str):
    svc = service()
    try:
        submission = svc.get_submission_model(submission_id)
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    author_files = submission.files.filter(file_type__in=AUTHOR_VISIBLE_FILE_TYPES)
    return render(
        request,
        "status.html",
        {"submission": submission, "author_files": author_files},
    )


@require_POST
def run_workflow_page(request: HttpRequest, submission_id: str):
    try:
        results = WorkflowEngine().run(submission_id)
        failed = [item for item in results if item.get("status") == "failed"]
        if failed:
            messages.error(request, "Обработка завершилась с ошибками. Проверьте результаты workflow.")
        else:
            messages.success(request, "Материал обработан: структура извлечена, DOCX оформлен, PDF и ZIP сформированы.")
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    except Exception as exc:
        messages.error(request, f"Не удалось запустить обработку: {exc}")
    return redirect("status", submission_id=submission_id)


@require_POST
def confirm_submission(request: HttpRequest, submission_id: str):
    svc = service()
    try:
        svc.update_submission_status(submission_id, "author_confirmed", "Автор подтвердил итоговый вариант.", "author")
        svc.update_submission_status(submission_id, "editor_review", "Материал передан редактору.", "system")
    except Exception:
        pass
    return redirect("status", submission_id=submission_id)


@require_POST
def upload_revision(request: HttpRequest, submission_id: str):
    uploaded_file = request.FILES.get("revision_docx")
    if not uploaded_file or not uploaded_file.name.lower().endswith(".docx"):
        return HttpResponseBadRequest("Можно загрузить только DOCX-файл.")
    svc = service()
    try:
        submission = svc.get_submission_model(submission_id)
    except ObjectDoesNotExist as exc:
        raise Http404("Заявка не найдена") from exc
    svc.save_uploaded_file(submission, "revision_docx", uploaded_file)
    try:
        svc.update_submission_status(submission_id, "uploaded", "Автор загрузил исправленную версию.", "author")
    except Exception:
        svc.add_event(submission_id, "revision_uploaded", {"filename": uploaded_file.name})
    return redirect("status", submission_id=submission_id)


def download_file(request: HttpRequest, file_id: int):
    try:
        file_row = SubmissionFile.objects.get(pk=file_id)
    except SubmissionFile.DoesNotExist as exc:
        raise Http404("Файл не найден") from exc
    if file_row.file_type not in AUTHOR_VISIBLE_FILE_TYPES:
        raise Http404("Служебный файл недоступен для скачивания.")
    path = resolve_stored_file_path(file_row.path)
    if not path.exists():
        raise Http404("Файл отсутствует в хранилище")
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)


def api_index(request: HttpRequest):
    return JsonResponse(
        {
            "service": "conference-system-django-core",
            "endpoints": [
                "GET /api/health/",
                "GET /api/organizations/?q=...",
                "GET|POST /api/submissions/",
                "GET /api/submissions/<submission_id>/",
                "PATCH /api/submissions/<submission_id>/status/",
                "POST /api/submissions/<submission_id>/checks/",
                "POST /api/submissions/<submission_id>/events/",
                "POST /api/submissions/<submission_id>/files/",
                "POST /api/submissions/<submission_id>/editor-decision/",
                "POST /api/submissions/<submission_id>/workflow/run/",
            ],
        },
        json_dumps_params={"ensure_ascii": False},
    )


def api_health(request: HttpRequest):
    return JsonResponse({"status": "ok", "service": "conference-system-django-core"})


def api_organizations(request: HttpRequest):
    q = request.GET.get("q")
    limit = int(request.GET.get("limit", "50"))
    data = service().list_organizations(q=q, limit=limit)
    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_submissions(request: HttpRequest):
    svc = service()
    if request.method == "GET":
        data = svc.list_submissions(issue_id=request.GET.get("issue_id"))
        return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})
    try:
        payload = parse_json_request(request)
        data = svc.create_submission(payload)
        return JsonResponse(data, status=201, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


def api_submission_detail(request: HttpRequest, submission_id: str):
    try:
        data = service().get_submission(submission_id)
        return JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@require_http_methods(["PATCH", "POST"])
def api_submission_status(request: HttpRequest, submission_id: str):
    try:
        payload = parse_json_request(request)
        data = service().update_submission_status(
            submission_id,
            payload.get("status", ""),
            payload.get("comment", ""),
            payload.get("changed_by", "system"),
        )
        return JsonResponse(data, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
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


@csrf_exempt
@require_POST
def api_editor_decision(request: HttpRequest, submission_id: str):
    try:
        payload = parse_json_request(request)
        row = service().save_editor_decision(
            submission_id,
            payload.get("decision", "editor_review"),
            payload.get("editor_name", "editor"),
            payload.get("comment", ""),
        )
        return JsonResponse(row, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@require_POST
def api_workflow_run(request: HttpRequest, submission_id: str):
    try:
        results = WorkflowEngine().run(submission_id)
        return JsonResponse({"status": "completed", "results": results}, json_dumps_params={"ensure_ascii": False})
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Заявка не найдена"}, status=404, json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})
