from __future__ import annotations

from sqlalchemy.orm import Session

from conference_system.core.file_storage import ensure_demo_result_files
from conference_system.submissions.service import SubmissionService


def seed_demo_data(db: Session) -> None:
    service = SubmissionService(db)
    service.ensure_defaults()
    if service.list_submissions():
        return
    data = {
        "conference_id": "ai_quarterly_conf",
        "issue_id": "2026_q1",
        "author_contact": {
            "full_name": "Иванов Иван Иванович",
            "email": "ivanov@example.com",
            "organization": "ТГТУ",
        },
        "metadata": {
            "title_ru": "Применение нейросетей для анализа учебных текстов",
            "title_en": "",
            "authors": [
                {"full_name": "Иванов И.И.", "organization": "ТГТУ", "email": "ivanov@example.com"}
            ],
            "supervisor": "Петров П.П.",
            "section": "Искусственный интеллект в образовании",
            "keywords_ru": ["нейросети", "образование", "анализ текста"],
            "abstract_ru": "Демонстрационная заявка для проверки ядра системы.",
        },
    }
    submission = service.create_submission(data)
    sid = submission["submission_id"]
    ensure_demo_result_files(sid)
    service.save_submission_file(sid, "formatted_docx", f"storage/submissions/{sid}/formatted_material.docx")
    service.save_submission_file(sid, "formatted_pdf", f"storage/submissions/{sid}/formatted_material.pdf")
    service.save_check_result(
        sid,
        {
            "check_id": "formal_structure_check",
            "title": "Формальная проверка структуры",
            "status": "warning",
            "risk_level": "low",
            "score": 0.8,
            "summary": "Демонстрационная проверка: существенных ошибок нет, но требуется ручной просмотр.",
            "warnings": [
                {
                    "code": "demo_warning",
                    "message": "Это тестовое предупреждение.",
                    "location": "Демонстрационный материал",
                    "recommendation": "Заменить на результат реального модуля проверок.",
                }
            ],
            "errors": [],
        },
    )
    service.update_submission_status(sid, "needs_author_review", "Демонстрационный материал готов к согласованию.")
