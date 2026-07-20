from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from reportlab.pdfgen import canvas

from submissions.models import Submission
from submissions.services import SubmissionService
from tema.editorial.services import build_issue_collection


class Command(BaseCommand):
    help = "Создаёт тестовый выпуск из пяти материалов и собирает PDF."

    def handle(self, *args, **options):
        service = SubmissionService()
        service.ensure_defaults()
        issue_id = settings.ISSUE_DEFAULT_ID

        for number in range(1, 6):
            uploaded = SimpleUploadedFile(
                f"paper_{number}.docx",
                b"PK demo docx placeholder",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            data = service.create_submission(
                {
                    "issue_id": issue_id,
                    "author_contact": {
                        "full_name": f"Тестовый Автор {number}",
                        "email": f"author{number}@example.com",
                        "organization": "Тестовая организация",
                    },
                    "metadata": {
                        "title_ru": f"Тестовый материал {number}",
                        "section": "Секция A" if number <= 3 else "Секция B",
                        "authors": [],
                    },
                },
                uploaded_file=uploaded,
            )
            submission_id = data["submission_id"]
            submission_dir = Path(settings.SUBMISSIONS_STORAGE_DIR) / submission_id
            pdf_path = submission_dir / "formatted_material.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf = canvas.Canvas(str(pdf_path))
            pdf.drawString(72, 760, f"Test material {number}")
            pdf.save()
            service.save_or_update_file_path(submission_id, "formatted_pdf", str(pdf_path))
            Submission.objects.filter(pk=submission_id).update(status="included_in_issue")

        result = build_issue_collection(issue_id)
        self.stdout.write(self.style.SUCCESS(f"Тестовый выпуск создан: {result['status']}"))
