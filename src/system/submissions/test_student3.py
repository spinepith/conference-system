from __future__ import annotations

import tempfile
import zipfile
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from reportlab.pdfgen import canvas

from submissions.models import EditorDecision, Submission, StatusHistory, WorkflowStageResult
from submissions.services import SubmissionService, resolve_stored_file_path
from tema.editorial import services as editorial_services
from tema.issue_builder.archive_page import ensure_archive_sticky_footer
from tema.pdf_export.pdf_exporter import ExportResult, export_docx_to_pdf
from tema.result_export.service import finalize_submission_files


class StudentThreeIntegrationTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.override = override_settings(
            MEDIA_ROOT=root,
            STORAGE_ROOT=root,
            SUBMISSIONS_STORAGE_DIR=root / "submissions",
            ISSUES_STORAGE_DIR=root / "issues",
        )
        self.override.enable()
        self.service = SubmissionService()
        self.service.ensure_defaults()
        self.client = Client()
        self.editor = get_user_model().objects.create_user(
            username="editor", first_name="Редактор", password="test-pass-123", is_staff=True
        )
        self.editor.groups.add(Group.objects.get_or_create(name="Editors")[0])
        self.client.force_login(self.editor)

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()

    def create_submission(self, *, status="uploaded", number=1):
        uploaded = SimpleUploadedFile(
            f"paper_{number}.docx",
            b"PK placeholder",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        data = self.service.create_submission(
            {
                "author_contact": {
                    "full_name": f"Иванов {number}",
                    "email": f"ivanov{number}@example.com",
                    "organization": "ТГТУ",
                },
                "metadata": {
                    "title_ru": f"Материал {number}",
                    "section": "ИИ в образовании" if number <= 3 else "Цифровые технологии",
                    "authors": [],
                },
            },
            uploaded_file=uploaded,
        )
        Submission.objects.filter(pk=data["submission_id"]).update(status=status)
        return data["submission_id"]

    def create_pdf(self, submission_id: str) -> Path:
        directory = Path(self.temp_dir.name) / "submissions" / submission_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "formatted_material.pdf"
        pdf = canvas.Canvas(str(path))
        pdf.drawString(72, 760, submission_id)
        pdf.save()
        self.service.save_or_update_file_path(submission_id, "formatted_pdf", str(path))
        return path

    def test_finalize_creates_pdf_manifest_and_zip(self):
        submission_id = self.create_submission()
        directory = Path(self.temp_dir.name) / "submissions" / submission_id
        for filename in ("formatted_material.docx", "extracted_metadata.json", "formatting_report.json"):
            (directory / filename).write_bytes(b"content")

        def fake_export(submission_dir):
            pdf_path = Path(submission_dir) / "formatted_material.pdf"
            pdf = canvas.Canvas(str(pdf_path))
            pdf.drawString(72, 760, "PDF")
            pdf.save()
            return ExportResult(status="success", pdf_path=str(pdf_path), attempts=1)

        with patch("tema.result_export.service.export_formatted_material", side_effect=fake_export):
            result = finalize_submission_files(directory)

        self.assertEqual(result["status"], "warning")
        self.assertTrue((directory / "formatted_material.pdf").is_file())
        self.assertTrue((directory / "result_manifest.json").is_file())
        self.assertTrue((directory / "result_package.zip").is_file())
        with zipfile.ZipFile(directory / "result_package.zip") as archive:
            names = archive.namelist()
            self.assertIn("formatted_material.docx", names)
            self.assertIn("formatted_material.pdf", names)
            self.assertNotIn("extracted_metadata.json", names)
            self.assertNotIn("formatting_report.json", names)
            self.assertNotIn("result_manifest.json", names)

        self.service.save_or_update_file_path(submission_id, "formatted_pdf", str(directory / "formatted_material.pdf"))
        self.service.save_or_update_file_path(submission_id, "result_package", str(directory / "result_package.zip"))

        pdf_response = self.client.get(f"/download/{submission_id}/formatted_pdf/")
        try:
            self.assertEqual(pdf_response.status_code, 200)
        finally:
            pdf_response.close()

        zip_response = self.client.get(f"/download/{submission_id}/result_package/")
        try:
            self.assertEqual(zip_response.status_code, 200)
        finally:
            zip_response.close()


    def test_author_page_hides_internal_json_files(self):
        submission_id = self.create_submission()
        directory = Path(self.temp_dir.name) / "submissions" / submission_id
        metadata_path = directory / "extracted_metadata.json"
        metadata_path.write_text("{}", encoding="utf-8")
        metadata_file = self.service.save_or_update_file_path(
            submission_id, "extracted_metadata", str(metadata_path)
        )

        formatted_path = directory / "formatted_material.docx"
        formatted_path.write_bytes(b"docx")
        self.service.save_or_update_file_path(submission_id, "formatted_docx", str(formatted_path))

        response = self.client.get(f"/status/{submission_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "formatted_docx")
        self.assertNotContains(response, "extracted_metadata")
        self.assertEqual(
            self.client.get(f"/download/{metadata_file['id']}/").status_code,
            404,
        )


    def test_old_pdf_does_not_mask_failed_conversion(self):
        directory = Path(self.temp_dir.name) / "stale"
        directory.mkdir(parents=True)
        docx = directory / "formatted_material.docx"
        docx.write_bytes(b"docx")
        old_pdf = directory / "formatted_material.pdf"
        old_pdf.write_bytes(b"%PDF-old")

        with patch("tema.pdf_export.pdf_exporter._detect_soffice_bin", return_value="fake-soffice"), patch(
            "tema.pdf_export.pdf_exporter.subprocess.run",
            return_value=CompletedProcess([], 1, stdout="", stderr="conversion failed"),
        ):
            result = export_docx_to_pdf(docx, directory, retries=0)

        self.assertEqual(result.status, "failed")
        self.assertFalse(old_pdf.exists())

    def test_issue_list_route_is_not_captured_as_submission(self):
        response = self.client.get("/editor/issues/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editorial/issue_list.html")

    def test_editor_panel_and_decision_history(self):
        submission_id = self.create_submission(status="editor_review")
        self.assertEqual(self.client.get("/editor/").status_code, 200)
        self.assertEqual(self.client.get(f"/editor/{submission_id}/").status_code, 200)
        response = self.client.post(
            f"/editor/{submission_id}/decision/",
            {"decision": "accept", "editor_name": "Подложное имя", "comment": "Принято"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Submission.objects.get(pk=submission_id).status, "accepted")
        decision = EditorDecision.objects.get(submission_id=submission_id, decision="accept")
        self.assertEqual(decision.editor, self.editor)
        self.assertEqual(decision.editor_name, "Редактор")
        self.assertTrue(StatusHistory.objects.filter(submission_id=submission_id, to_status="accepted").exists())

    def test_editor_can_replace_previous_decision(self):
        submission_id = self.create_submission(status="editor_review")
        decisions = [
            ("revision", "needs_revision"),
            ("accept", "accepted"),
            ("reject", "rejected"),
            ("return_to_author", "needs_author_review"),
        ]
        for decision, expected_status in decisions:
            response = self.client.post(
                f"/editor/{submission_id}/decision/",
                {"decision": decision, "editor_name": "Подложное имя", "comment": decision},
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Submission.objects.get(pk=submission_id).status, expected_status)

        self.assertEqual(
            EditorDecision.objects.filter(submission_id=submission_id).count(),
            len(decisions),
        )

    @override_settings(TIME_ZONE="Europe/Moscow", USE_TZ=True)
    def test_editor_workflow_displays_local_time(self):
        submission_id = self.create_submission(status="editor_review")
        WorkflowStageResult.objects.create(
            submission_id=submission_id,
            stage_id="test_stage",
            title="Тест",
            status="success",
            message="Готово",
            started_at=datetime(2026, 7, 21, 12, 0, 0, tzinfo=dt_timezone.utc),
            finished_at=datetime(2026, 7, 21, 12, 0, 5, tzinfo=dt_timezone.utc),
        )

        response = self.client.get(f"/editor/{submission_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "21.07.2026 15:00:00")
        self.assertContains(response, "21.07.2026 15:00:05")

    def test_existing_archive_html_gets_sticky_footer_upgrade(self):
        old_html = (
            '<style>*{box-sizing:border-box}html{scroll-behavior:smooth}'
            'body{margin:0;color:#111}main{padding:65px 0}</style>'
        )
        upgraded = ensure_archive_sticky_footer(old_html)
        self.assertIn('body{display:flex', upgraded)
        self.assertIn('min-height:100dvh', upgraded)
        self.assertIn('main{flex:1 0 auto', upgraded)

    def test_issue_collection_from_five_materials(self):
        issue_id = "2026_q1"
        submission_ids = []
        for number in range(1, 6):
            submission_id = self.create_submission(status="included_in_issue", number=number)
            self.create_pdf(submission_id)
            submission_ids.append(submission_id)

        result = editorial_services.build_issue_collection(issue_id)
        self.assertEqual(result["status"], "success")
        issue = editorial_services.issue_to_dict(issue_id)
        collection = resolve_stored_file_path(issue["files"]["collection_pdf"])
        archive = resolve_stored_file_path(issue["files"]["archive_page"])
        self.assertTrue(collection.is_file())
        self.assertTrue(archive.is_file())
        archive_html = archive.read_text(encoding="utf-8")
        self.assertIn("display:flex", archive_html)
        self.assertIn("min-height:100dvh", archive_html)
        self.assertIn("main{flex:1 0 auto", archive_html)
        self.assertGreater(collection.stat().st_size, 0)
        self.assertEqual(Submission.objects.filter(pk__in=submission_ids, status="published").count(), 5)
        self.assertEqual(self.client.get(f"/issues/{issue_id}/download/collection/").status_code, 200)
        self.assertEqual(self.client.get(f"/archive/{issue_id}/").status_code, 200)
