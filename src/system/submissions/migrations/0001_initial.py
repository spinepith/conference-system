# Generated manually for the educational MVP.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Conference",
            fields=[
                ("conference_id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Issue",
            fields=[
                ("issue_id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("year", models.PositiveIntegerField(default=2026)),
                ("quarter", models.PositiveSmallIntegerField(default=1)),
                ("published_at", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("conference", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="issues", to="submissions.conference")),
            ],
        ),
        migrations.CreateModel(
            name="Submission",
            fields=[
                ("submission_id", models.CharField(max_length=40, primary_key=True, serialize=False)),
                ("status", models.CharField(db_index=True, default="uploaded", max_length=40)),
                ("author_contact", models.JSONField(default=dict)),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conference", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submissions", to="submissions.conference")),
                ("issue", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submissions", to="submissions.issue")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=400, unique=True)),
                ("normalized_name", models.CharField(db_index=True, max_length=400, unique=True)),
                ("source", models.CharField(default="user", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by_submission", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_organizations", to="submissions.submission")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Author",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=255)),
                ("organization", models.CharField(blank=True, max_length=400)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="authors", to="submissions.submission")),
            ],
        ),
        migrations.CreateModel(
            name="SubmissionFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file_type", models.CharField(max_length=80)),
                ("path", models.CharField(max_length=600)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="files", to="submissions.submission")),
            ],
            options={"ordering": ["file_type", "-uploaded_at"]},
        ),
        migrations.CreateModel(
            name="CheckResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("check_id", models.CharField(max_length=120)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(default="completed", max_length=40)),
                ("risk_level", models.CharField(default="low", max_length=40)),
                ("score", models.FloatField(blank=True, null=True)),
                ("summary", models.TextField(blank=True)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("errors", models.JSONField(blank=True, default=list)),
                ("raw_model_response_path", models.CharField(blank=True, max_length=600)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checks", to="submissions.submission")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkflowStageResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage_id", models.CharField(max_length=120)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(default="success", max_length=40)),
                ("message", models.TextField(blank=True)),
                ("result_json", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workflow_results", to="submissions.submission")),
            ],
            options={"ordering": ["-finished_at", "-id"]},
        ),
        migrations.CreateModel(
            name="StatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_status", models.CharField(blank=True, max_length=40)),
                ("to_status", models.CharField(max_length=40)),
                ("changed_by", models.CharField(default="system", max_length=120)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("comment", models.TextField(blank=True)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_history", to="submissions.submission")),
            ],
            options={"ordering": ["changed_at"]},
        ),
        migrations.CreateModel(
            name="EditorDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(max_length=40)),
                ("editor_name", models.CharField(default="editor", max_length=160)),
                ("comment", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="editor_decisions", to="submissions.submission")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="EventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="submissions.submission")),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
