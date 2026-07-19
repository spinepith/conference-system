from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from submissions.models import Organization, Submission
from submissions.services import SubmissionService
from submissions.workflow import WorkflowEngine


class ConferenceSystemTests(TestCase):
    def setUp(self):
        self.service = SubmissionService()
        self.service.ensure_defaults()

    def test_seed_organizations_loaded(self):
        self.assertTrue(Organization.objects.exists())

    def test_new_organization_is_saved(self):
        file = SimpleUploadedFile("paper.docx", b"docx")
        submission = self.service.create_submission(
            {
                "author_contact": {
                    "full_name": "Тестовый Автор",
                    "email": "test@example.com",
                    "organization": "Новая тестовая организация",
                },
                "metadata": {"title_ru": "Тестовый материал", "authors": []},
            },
            uploaded_file=file,
        )
        self.assertTrue(Submission.objects.filter(pk=submission["submission_id"]).exists())
        self.assertTrue(Organization.objects.filter(name="Новая тестовая организация").exists())

    def test_api_submissions_list(self):
        response = Client().get("/api/submissions/")
        self.assertEqual(response.status_code, 200)

    def test_workflow_runs(self):
        file = SimpleUploadedFile("paper.docx", b"docx")
        submission = self.service.create_submission(
            {
                "author_contact": {"full_name": "Автор", "email": "a@example.com", "organization": "Организация"},
                "metadata": {"title_ru": "Материал", "authors": []},
            },
            uploaded_file=file,
        )
        results = WorkflowEngine().run(submission["submission_id"])
        self.assertGreaterEqual(len(results), 1)
