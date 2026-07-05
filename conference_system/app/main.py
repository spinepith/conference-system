from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from conference_system.app.config import settings
from conference_system.app.database import get_db, init_db
from conference_system.app.seed import seed_demo_data
from conference_system.core.demo_stages import register_demo_stages
from conference_system.core.file_storage import ensure_demo_result_files
from conference_system.core.plugin_registry import registry
from conference_system.core.workflow import WorkflowEngine
from conference_system.submissions.schemas import (
    CheckResultIn,
    EditorDecisionIn,
    EventIn,
    StatusUpdate,
    SubmissionCreate,
)
from conference_system.submissions.service import SubmissionService

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "author_ui" / "templates"))

app = FastAPI(title="Conference System MVP", version="1.0.0")

static_dir = BASE_DIR / "author_ui" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    register_demo_stages()
    if settings.create_demo_data:
        from conference_system.app.database import SessionLocal

        with SessionLocal() as db:
            seed_demo_data(db)


def service(db: Session = Depends(get_db)) -> SubmissionService:
    return SubmissionService(db)


def not_found_to_http(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "conference-system-core"}


@app.post("/api/submissions")
def api_create_submission(payload: SubmissionCreate, svc: SubmissionService = Depends(service)):
    return svc.create_submission(payload.model_dump())


@app.get("/api/submissions")
def api_list_submissions(issue_id: str | None = None, svc: SubmissionService = Depends(service)):
    return svc.list_submissions(issue_id)


@app.get("/api/submissions/{submission_id}")
def api_get_submission(submission_id: str, svc: SubmissionService = Depends(service)):
    try:
        return svc.get_submission(submission_id)
    except KeyError as exc:
        raise not_found_to_http(exc)


@app.patch("/api/submissions/{submission_id}/status")
def api_update_status(submission_id: str, payload: StatusUpdate, svc: SubmissionService = Depends(service)):
    try:
        return svc.update_submission_status(submission_id, payload.status, payload.comment, payload.changed_by)
    except KeyError as exc:
        raise not_found_to_http(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/submissions/{submission_id}/checks")
def api_save_check_result(submission_id: str, payload: CheckResultIn, svc: SubmissionService = Depends(service)):
    try:
        svc.save_check_result(submission_id, payload.model_dump())
        return {"status": "saved"}
    except KeyError as exc:
        raise not_found_to_http(exc)


@app.post("/api/submissions/{submission_id}/events")
def api_add_event(submission_id: str, payload: EventIn, svc: SubmissionService = Depends(service)):
    try:
        svc.add_event(submission_id, payload.event_type, payload.payload)
        return {"status": "saved"}
    except KeyError as exc:
        raise not_found_to_http(exc)


@app.post("/api/submissions/{submission_id}/files")
async def api_upload_file(
    submission_id: str,
    file_type: str = Form(...),
    file: UploadFile = File(...),
    svc: SubmissionService = Depends(service),
):
    if file_type in {"original_docx", "revision_docx"} and not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Можно загружать только DOCX-файлы.")
    try:
        return svc.save_upload_file(submission_id, file_type, file.file, file.filename, file.content_type or "")
    except KeyError as exc:
        raise not_found_to_http(exc)


@app.post("/api/submissions/{submission_id}/editor-decision")
def api_editor_decision(submission_id: str, payload: EditorDecisionIn, svc: SubmissionService = Depends(service)):
    try:
        return svc.save_editor_decision(submission_id, payload.decision, payload.editor_name, payload.comment)
    except KeyError as exc:
        raise not_found_to_http(exc)


@app.post("/api/submissions/{submission_id}/workflow/run")
def api_run_workflow(submission_id: str):
    try:
        return WorkflowEngine().run_submission(submission_id)
    except KeyError as exc:
        raise not_found_to_http(exc)


@app.get("/api/workflow/stages")
def api_workflow_stages():
    return [
        {
            "stage_id": stage.stage_id,
            "title": stage.title,
            "description": stage.description,
            "enabled": stage.enabled,
        }
        for stage in registry.list()
    ]


@app.get("/", response_class=HTMLResponse)
def index(request: Request, svc: SubmissionService = Depends(service)):
    submissions = svc.list_submissions()
    return templates.TemplateResponse(request, "index.html", {"submissions": submissions})


@app.get("/submit", response_class=HTMLResponse)
def submit_page(request: Request):
    return templates.TemplateResponse(request, "submit.html", {"error": None})


@app.post("/submit", response_class=HTMLResponse)
async def submit_form(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    organization: str = Form(""),
    title_ru: str = Form(...),
    section: str = Form(""),
    coauthors: str = Form(""),
    supervisor: str = Form(""),
    abstract_ru: str = Form(""),
    keywords_ru: str = Form(""),
    docx_file: UploadFile = File(...),
    svc: SubmissionService = Depends(service),
):
    if not docx_file.filename.lower().endswith(".docx"):
        return templates.TemplateResponse(
            "submit.html",
            {"request": request, "error": "Можно загрузить только файл в формате DOCX."},
            status_code=400,
        )
    authors = [{"full_name": full_name, "email": email, "organization": organization}]
    for name in [part.strip() for part in coauthors.split(",") if part.strip()]:
        authors.append({"full_name": name, "email": "", "organization": organization})
    data = {
        "conference_id": "ai_quarterly_conf",
        "issue_id": "2026_q1",
        "author_contact": {"full_name": full_name, "email": email, "organization": organization},
        "metadata": {
            "title_ru": title_ru,
            "authors": authors,
            "supervisor": supervisor,
            "section": section,
            "keywords_ru": [kw.strip() for kw in keywords_ru.split(",") if kw.strip()],
            "abstract_ru": abstract_ru,
        },
    }
    submission = svc.create_submission(data)
    submission = svc.save_upload_file(
        submission["submission_id"], "original_docx", docx_file.file, docx_file.filename, docx_file.content_type or ""
    )
    return RedirectResponse(url=f"/status/{submission['submission_id']}", status_code=303)


@app.get("/status/{submission_id}", response_class=HTMLResponse)
def status_page(request: Request, submission_id: str, svc: SubmissionService = Depends(service)):
    try:
        submission = svc.get_submission(submission_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return templates.TemplateResponse(request, "status.html", {"submission": submission})


@app.post("/status/{submission_id}/confirm")
def author_confirm(submission_id: str, svc: SubmissionService = Depends(service)):
    try:
        svc.update_submission_status(submission_id, "author_confirmed", "Автор подтвердил итоговый вариант.", "author")
        svc.update_submission_status(submission_id, "editor_review", "Материал передан редактору.", "system")
    except KeyError as exc:
        raise not_found_to_http(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/status/{submission_id}", status_code=303)


@app.post("/status/{submission_id}/revision")
async def upload_revision(
    submission_id: str,
    revision_file: UploadFile = File(...),
    svc: SubmissionService = Depends(service),
):
    if not revision_file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Можно загрузить только DOCX-файл.")
    try:
        svc.save_upload_file(submission_id, "revision_docx", revision_file.file, revision_file.filename, revision_file.content_type or "")
    except KeyError as exc:
        raise not_found_to_http(exc)
    return RedirectResponse(url=f"/status/{submission_id}", status_code=303)


@app.get("/download/{submission_id}/{file_type}")
def download_file(submission_id: str, file_type: str, svc: SubmissionService = Depends(service)):
    try:
        submission = svc.get_submission(submission_id)
    except KeyError as exc:
        raise not_found_to_http(exc)
    path = submission.get("files", {}).get(file_type)
    if not path:
        # For demo: result placeholders can be created manually by external modules, but not invented for original files.
        if file_type in {"formatted_docx", "formatted_pdf", "check_report"}:
            ensure_demo_result_files(submission_id)
            default_map = {
                "formatted_docx": f"storage/submissions/{submission_id}/formatted_material.docx",
                "formatted_pdf": f"storage/submissions/{submission_id}/formatted_material.pdf",
                "check_report": f"storage/submissions/{submission_id}/check_report.json",
            }
            path = default_map[file_type]
            svc.save_submission_file(submission_id, file_type, path)
        else:
            raise HTTPException(status_code=404, detail="Файл ещё не создан.")
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл отсутствует на диске.")
    return FileResponse(path=str(file_path), filename=file_path.name)
