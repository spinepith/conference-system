import os
from io import BytesIO

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conference_project.settings")

import django
from django.core.files.uploadedfile import SimpleUploadedFile

django.setup()

from submissions.services import SubmissionService

content = BytesIO(b"Demo DOCX placeholder for conference MVP")
file = SimpleUploadedFile("demo.docx", content.read(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
service = SubmissionService()
submission = service.create_submission(
    {
        "author_contact": {
            "full_name": "Иванов Иван Иванович",
            "email": "ivanov@example.com",
            "organization": "Московский государственный университет имени М. В. Ломоносова",
        },
        "metadata": {
            "title_ru": "Применение нейросетей для анализа учебных текстов",
            "section": "Искусственный интеллект в образовании",
            "keywords_ru": ["нейросети", "образование", "анализ текста"],
            "abstract_ru": "Демонстрационная заявка для проверки ядра системы.",
            "authors": [],
        },
    },
    uploaded_file=file,
)
print(submission["submission_id"])
