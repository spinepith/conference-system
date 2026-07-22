from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from submissions.models import CheckResult, EditorDecision, Submission
from submissions.services import SubmissionService
from submissions.workflow import WorkflowEngine


class AuthorizationTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.settings_override = override_settings(
            MEDIA_ROOT=root,
            STORAGE_ROOT=root,
            SUBMISSIONS_STORAGE_DIR=root / "submissions",
            ISSUES_STORAGE_DIR=root / "issues",
            INTERNAL_API_TOKEN="internal-test-token",
        )
        self.settings_override.enable()

        users = get_user_model()
        self.author = users.objects.create_user(
            username="author-one",
            first_name="Автор Один",
            email="author1@example.com",
            password="test-pass-123",
        )
        self.other_author = users.objects.create_user(
            username="author-two",
            first_name="Автор Два",
            email="author2@example.com",
            password="test-pass-123",
        )
        self.editor = users.objects.create_user(
            username="editor",
            first_name="Главный Редактор",
            password="test-pass-123",
            is_staff=True,
        )
        self.administrator = users.objects.create_user(
            username="administrator",
            first_name="Администратор",
            password="test-pass-123",
            is_staff=True,
        )
        authors_group, _ = Group.objects.get_or_create(name="Authors")
        editors_group, _ = Group.objects.get_or_create(name="Editors")
        self.author.groups.add(authors_group)
        self.other_author.groups.add(authors_group)
        self.editor.groups.add(editors_group)

        self.service = SubmissionService()
        self.service.ensure_defaults()
        self.author_submission = self._create_submission(self.author, 1)
        self.other_submission = self._create_submission(self.other_author, 2)

    def tearDown(self):
        self.settings_override.disable()
        self.temp_dir.cleanup()

    def _create_submission(self, owner, number: int) -> str:
        uploaded = SimpleUploadedFile(
            f"paper_{number}.docx",
            b"PK placeholder",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        data = self.service.create_submission(
            {
                "author_contact": {
                    "full_name": owner.get_full_name(),
                    "email": owner.email,
                    "organization": "ТГТУ",
                },
                "metadata": {
                    "title_ru": f"Материал {number}",
                    "section": "ИИ",
                    "authors": [],
                },
            },
            uploaded_file=uploaded,
            owner=owner,
        )
        return data["submission_id"]

    def test_registration_creates_author_role(self):
        client = Client()
        response = client.post(
            "/accounts/register/",
            {
                "username": "new-author",
                "full_name": "Новый Автор",
                "email": "new-author@example.com",
                "password1": "Complex-pass-123",
                "password2": "Complex-pass-123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username="new-author")
        self.assertTrue(user.groups.filter(name="Authors").exists())

    def test_guest_is_redirected_to_login(self):
        client = Client()
        self.assertEqual(client.get("/submit/").status_code, 302)
        self.assertEqual(client.get(f"/status/{self.author_submission}/").status_code, 302)
        self.assertEqual(client.get("/editor/").status_code, 302)

    def test_author_sees_only_owned_submission(self):
        client = Client()
        client.force_login(self.author)
        self.assertEqual(client.get(f"/status/{self.author_submission}/").status_code, 200)
        self.assertEqual(client.get(f"/status/{self.other_submission}/").status_code, 404)

        response = client.get("/api/submissions/")
        self.assertEqual(response.status_code, 200)
        ids = {row["submission_id"] for row in response.json()}
        self.assertEqual(ids, {self.author_submission})

    def test_author_cannot_open_editor_panel(self):
        client = Client()
        client.force_login(self.author)
        self.assertEqual(client.get("/editor/").status_code, 403)
        self.assertEqual(client.get("/editor/issues/").status_code, 403)

    def test_editor_can_view_all_and_identity_is_not_taken_from_post(self):
        client = Client()
        client.force_login(self.editor)
        self.assertEqual(client.get("/editor/").status_code, 200)
        self.assertEqual(client.get(f"/editor/{self.author_submission}/").status_code, 200)

        Submission.objects.filter(pk=self.author_submission).update(status="editor_review")
        response = client.post(
            f"/editor/{self.author_submission}/decision/",
            {
                "decision": "accept",
                "editor_name": "Подложное имя",
                "comment": "Принято",
            },
        )
        self.assertEqual(response.status_code, 302)
        decision = EditorDecision.objects.get(submission_id=self.author_submission)
        self.assertEqual(decision.editor, self.editor)
        self.assertEqual(decision.editor_name, "Главный Редактор")


    def test_administrator_is_not_editor_or_author_automatically(self):
        client = Client()
        client.force_login(self.administrator)

        public_page = client.get("/")
        self.assertEqual(public_page.status_code, 200)
        self.assertContains(public_page, "Публикуйте исследования")
        self.assertEqual(client.get("/cabinet/").status_code, 302)
        dashboard = client.get("/cabinet/admin/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Администрирование платформы")
        self.assertNotContains(dashboard, "Мои материалы")
        self.assertEqual(client.get("/editor/").status_code, 403)
        self.assertEqual(client.get("/editor/issues/").status_code, 403)
        self.assertEqual(client.get("/submit/").status_code, 403)

    def test_public_conferences_are_separate_from_author_dashboard(self):
        client = Client()
        client.force_login(self.author)

        public_page = client.get("/")
        self.assertEqual(public_page.status_code, 200)
        self.assertContains(public_page, "Публикуйте исследования")

        conferences = client.get("/conferences/")
        self.assertEqual(conferences.status_code, 200)
        self.assertContains(conferences, "Открытые конференции")
        self.assertContains(conferences, "2026_q1")

        dashboard = client.get("/cabinet/materials/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Мои материалы")
        self.assertNotContains(dashboard, "Доступные конференции")

    def test_author_sees_available_conference_and_selects_issue(self):
        client = Client()
        client.force_login(self.author)

        conferences = client.get("/conferences/")
        self.assertEqual(conferences.status_code, 200)
        self.assertContains(conferences, "Открытые конференции")
        self.assertContains(conferences, "2026_q1")

        response = client.post(
            "/submit/",
            {
                "issue_id": "2026_q1",
                "full_name": "Автор Один",
                "email": "author1@example.com",
                "organization": "ТГТУ",
                "title_ru": "Новая работа",
                "section": "ИИ",
                "authors_json": "[]",
                "supervisor": "",
                "abstract_ru": "",
                "keywords_ru": "ИИ",
                "docx_file": SimpleUploadedFile(
                    "new-paper.docx",
                    b"PK placeholder",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Submission.objects.filter(owner=self.author, metadata__title_ru="Новая работа").get()
        self.assertEqual(created.issue_id, "2026_q1")
        self.assertTrue(created.access_token)
        self.assertLessEqual(len(created.access_token), 64)

    @override_settings(
        CREATE_DEMO_ACCOUNTS=True,
        DEMO_AUTHOR_USERNAME="demo-author",
        DEMO_EDITOR_USERNAME="demo-editor",
        DEMO_ADMIN_USERNAME="demo-admin",
    )
    def test_demo_account_command_creates_all_roles(self):
        call_command("setup_demo_accounts")
        users = get_user_model().objects
        author = users.get(username="demo-author")
        editor = users.get(username="demo-editor")
        admin = users.get(username="demo-admin")
        self.assertTrue(author.check_password("demo-author"))
        self.assertTrue(author.groups.filter(name="Authors").exists())
        self.assertTrue(editor.check_password("demo-editor"))
        self.assertTrue(editor.groups.filter(name="Editors").exists())
        self.assertTrue(admin.check_password("demo-admin"))
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_editor_card_uses_human_readable_warning_summary(self):
        CheckResult.objects.create(
            submission_id=self.author_submission,
            check_id="semantic_quality_check",
            title="Смысловая проверка",
            status="warning",
            risk_level="medium",
            warnings=[
                {"code": "weak_ai_connection"},
                {"code": "no_research_or_project_component"},
                {"message": "no_result"},
                "topic_relevance_weak",
                {"code": "no_references"},
            ],
        )
        client = Client()
        client.force_login(self.editor)
        response = client.get(f"/editor/{self.author_submission}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Связь материала с тематикой искусственного интеллекта")
        self.assertContains(response, "Не выявлена исследовательская или проектная составляющая")
        self.assertContains(response, "В материале не представлены результаты работы")
        self.assertContains(response, "Тематическое соответствие конференции выражено слабо")
        self.assertContains(response, "Не найден список литературы")
        self.assertNotContains(response, "weak_ai_connection")
        self.assertNotContains(response, "no_research_or_project_component")
        self.assertNotContains(response, "topic_relevance_weak")

    def test_successful_workflow_retry_clears_error_status(self):
        Submission.objects.filter(pk=self.author_submission).update(status="error")

        class SuccessfulRetryStage:
            stage_id = "successful_retry"
            title = "Успешный повтор"
            enabled = True

            def run(self, submission):
                self.received_status = submission["status"]
                return {
                    "status": "success",
                    "message": "Повторная обработка выполнена.",
                    "next_status": "structure_extracted",
                }

        stage = SuccessfulRetryStage()
        with patch.object(WorkflowEngine, "_register_default_stages"), patch(
            "submissions.workflow.registry.list", return_value=[stage]
        ):
            WorkflowEngine().run(self.author_submission)

        self.assertEqual(stage.received_status, "uploaded")
        self.assertEqual(
            Submission.objects.get(pk=self.author_submission).status,
            "structure_extracted",
        )

    def test_editor_decision_ui_is_unambiguous_and_marks_acceptance(self):
        client = Client()
        client.force_login(self.editor)
        url = f"/editor/{self.author_submission}/"

        response = client.get(url)
        self.assertNotContains(response, "На согласование")
        self.assertContains(response, "На доработку")

        Submission.objects.filter(pk=self.author_submission).update(status="accepted")
        response = client.get(url)
        self.assertContains(response, "✓ Принято")
        self.assertContains(response, 'aria-pressed="true"')
        self.assertNotContains(response, 'name="decision" value="accept"')
        self.assertContains(response, 'name="decision" value="reject"')
        self.assertContains(response, 'name="decision" value="revision"')
        self.assertContains(response, "Включить в выпуск")

    def test_issue_buttons_follow_submission_status(self):
        client = Client()
        client.force_login(self.editor)
        url = f"/editor/{self.author_submission}/"

        response = client.get(url)
        self.assertNotContains(response, ">Включить в выпуск<", html=False)
        self.assertNotContains(response, ">Исключить из выпуска<", html=False)

        Submission.objects.filter(pk=self.author_submission).update(status="accepted")
        response = client.get(url)
        self.assertContains(response, "Включить в выпуск")
        self.assertNotContains(response, "Исключить из выпуска")

        Submission.objects.filter(pk=self.author_submission).update(status="included_in_issue")
        response = client.get(url)
        self.assertNotContains(response, ">Включить в выпуск<", html=False)
        self.assertContains(response, "Исключить из выпуска")

    def test_editor_file_download_control_has_non_overlapping_layout(self):
        client = Client()
        client.force_login(self.editor)
        response = client.get(f"/editor/{self.author_submission}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="editor-file-card"')
        self.assertContains(response, 'class="button button--ghost button--small editor-file-card__download"')
        self.assertContains(response, "Исходный материал")
        self.assertContains(response, "original.docx")

    def test_editor_can_change_acceptance_before_issue_inclusion(self):
        client = Client()
        client.force_login(self.editor)
        Submission.objects.filter(pk=self.author_submission).update(status="accepted")

        response = client.post(
            f"/editor/{self.author_submission}/decision/",
            {"decision": "revision", "comment": "Нужно исправить материал."},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Submission.objects.get(pk=self.author_submission).status,
            "needs_revision",
        )

    def test_editor_sidebar_does_not_show_api_section(self):
        client = Client()
        client.force_login(self.editor)
        response = client.get("/editor/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, ">API<", html=False)

    def test_archive_uses_role_appropriate_action_without_decorative_dash(self):
        client = Client()
        client.force_login(self.editor)
        response = client.get("/archive/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Открытая наука")
        self.assertContains(response, "Посмотреть конференции")
        self.assertNotContains(response, "Подать новый материал")
        self.assertContains(response, 'class="archive-hero__kicker"')


    def test_author_file_download_control_has_non_overlapping_layout(self):
        client = Client()
        client.force_login(self.author)
        response = client.get(f"/status/{self.author_submission}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="author-file-card"')
        self.assertContains(response, 'class="button button--small button--secondary author-file-card__download"')
        self.assertContains(response, "Исходный материал")
        self.assertContains(response, "original.docx")
        self.assertNotContains(response, "original_docx")

    def test_automatic_feedback_is_editor_only_until_revision_requested(self):
        CheckResult.objects.create(
            submission_id=self.author_submission,
            check_id="restricted_content_check",
            title="Проверка чувствительных сведений",
            status="warning",
            risk_level="medium",
            summary="Найден фрагмент, который необходимо проверить перед публикацией.",
            warnings=[
                {
                    "code": "unknown_manual_review_code",
                    "message": "unknown_manual_review_code",
                    "location": "Раздел 2",
                    "recommendation": "Уточните источник приведённых данных.",
                }
            ],
            errors=[
                {
                    "code": "document_number",
                    "location": "Приложение",
                    "recommendation": "Удалите номер документа из открытой версии.",
                }
            ],
            flagged_fragments=[
                {
                    "fragment": "Паспорт: 00 00 000000",
                    "risk_type": "personal_data",
                    "reason": "Возможное раскрытие персональных данных.",
                    "recommendation": "Обезличьте этот фрагмент.",
                }
            ],
            author_comment="Перед повторной отправкой обезличьте данные и уточните источник.",
            editor_comment="Проверьте отмеченный фрагмент и источник данных вручную.",
        )

        editor_client = Client()
        editor_client.force_login(self.editor)
        editor_response = editor_client.get(f"/editor/{self.author_submission}/")
        self.assertContains(editor_response, "Проверьте отмеченный фрагмент")
        self.assertContains(editor_response, "Уточните источник приведённых данных")
        self.assertContains(editor_response, "Удалите номер документа")
        self.assertContains(editor_response, "Паспорт: 00 00 000000")
        self.assertNotContains(
            editor_response,
            "Автоматическая проверка обнаружила замечание, требующее внимания редактора.",
        )

        author_client = Client()
        author_client.force_login(self.author)
        author_response = author_client.get(f"/status/{self.author_submission}/")
        self.assertContains(author_response, "Результаты проверок изучает редактор")
        self.assertNotContains(author_response, "Паспорт: 00 00 000000")
        self.assertNotContains(author_response, "Уточните источник приведённых данных")
        author_api = author_client.get(f"/api/submissions/{self.author_submission}/").json()
        self.assertEqual(author_api["checks"], [])

        Submission.objects.filter(pk=self.author_submission).update(status="editor_review")
        editor_client.post(
            f"/editor/{self.author_submission}/decision/",
            {"decision": "revision", "comment": "Исправьте отмеченные автоматической проверкой фрагменты."},
        )
        author_response = author_client.get(f"/status/{self.author_submission}/")
        self.assertContains(author_response, "Комментарий редактора")
        self.assertContains(author_response, "Исправьте отмеченные автоматической проверкой фрагменты")
        self.assertContains(author_response, "Перед повторной отправкой обезличьте данные")
        self.assertContains(author_response, "Уточните источник приведённых данных")
        self.assertContains(author_response, "Паспорт: 00 00 000000")
        author_api = author_client.get(f"/api/submissions/{self.author_submission}/").json()
        self.assertEqual(len(author_api["checks"]), 1)
        self.assertEqual(
            author_api["editor_comment"],
            "Исправьте отмеченные автоматической проверкой фрагменты.",
        )

    def test_internal_api_requires_token(self):
        url = f"/api/submissions/{self.author_submission}/events/"
        client = Client()
        self.assertEqual(client.post(url, data='{"event_type":"test"}', content_type="application/json").status_code, 403)
        response = client.post(
            url,
            data='{"event_type":"test","payload":{"ok":true}}',
            content_type="application/json",
            HTTP_X_INTERNAL_TOKEN="internal-test-token",
        )
        self.assertEqual(response.status_code, 200)

    def test_public_pdf_is_available_only_after_publication(self):
        path = Path(self.temp_dir.name) / "submissions" / self.author_submission / "formatted.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4 test")
        self.service.save_or_update_file_path(self.author_submission, "formatted_pdf", str(path))

        client = Client()
        url = f"/archive/materials/{self.author_submission}.pdf"
        self.assertEqual(client.get(url).status_code, 404)
        Submission.objects.filter(pk=self.author_submission).update(status="published")
        response = client.get(url)
        try:
            self.assertEqual(response.status_code, 200)
        finally:
            response.close()

    def test_editor_summary_uses_docx_json_instead_of_llm_aggregation(self):
        submission_dir = Path(self.temp_dir.name) / "submissions" / self.author_submission
        submission_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = submission_dir / "extracted_metadata.json"
        formatting_path = submission_dir / "formatting_report.json"
        metadata_path.write_text(
            '''{
              "title": "Название из extracted_metadata.json",
              "authors": [{"full_name": "Автор Один"}],
              "organization": "ТГТУ",
              "objects": {"tables_count": 2, "figures_count": 1, "equations_count": 3},
              "warnings": ["Не удалось определить подпись к рисунку."]
            }''',
            encoding="utf-8",
        )
        formatting_path.write_text(
            '''{
              "status": "partial",
              "template_used": "conference_template_v1.docx",
              "filled_fields": ["title_ru", "authors", "body_text"],
              "missing_fields": ["abstract_ru", "references"],
              "warnings": ["Аннотация не найдена в исходном файле."],
              "output_docx": "formatted_material.docx"
            }''',
            encoding="utf-8",
        )
        self.service.save_or_update_file_path(
            self.author_submission,
            "extracted_metadata",
            str(metadata_path),
        )
        self.service.save_or_update_file_path(
            self.author_submission,
            "formatting_report",
            str(formatting_path),
        )
        CheckResult.objects.create(
            submission_id=self.author_submission,
            check_id="semantic_quality_check",
            title="Смысловая проверка",
            status="warning",
            risk_level="medium",
            summary="LLM-сводка, которая не должна попадать в верхнюю карточку.",
            warnings=[{"code": "weak_ai_connection"}],
        )

        client = Client()
        client.force_login(self.editor)
        response = client.get(f"/editor/{self.author_submission}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сводка DOCX-модуля")
        self.assertContains(response, "Название из extracted_metadata.json")
        self.assertContains(response, "DOCX оформлен с предупреждениями")
        self.assertContains(response, "Аннотация")
        self.assertContains(response, "Список литературы")
        self.assertContains(response, "Аннотация не найдена в исходном файле")
        self.assertContains(response, "таблиц — 2, рисунков — 1, формул — 3")
        self.assertNotContains(response, "Краткая сводка")
        self.assertNotContains(response, "Основные замечания")
