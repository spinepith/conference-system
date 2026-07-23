from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from submissions.models import EditorDecision, Submission
from submissions.services import SubmissionService


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
