from __future__ import annotations

from django.db import models


class Conference(models.Model):
    conference_id = models.CharField(max_length=80, primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class Issue(models.Model):
    issue_id = models.CharField(max_length=80, primary_key=True)
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name="issues")
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(default=2026)
    quarter = models.PositiveSmallIntegerField(default=1)
    published_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.issue_id} — {self.title}"


class Organization(models.Model):
    name = models.CharField(max_length=400, unique=True)
    normalized_name = models.CharField(max_length=400, unique=True, db_index=True)
    source = models.CharField(max_length=32, default="user")
    created_by_submission = models.ForeignKey(
        "Submission", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_organizations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Submission(models.Model):
    submission_id = models.CharField(max_length=40, primary_key=True)
    conference = models.ForeignKey(Conference, on_delete=models.PROTECT, related_name="submissions")
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name="submissions")
    authors = models.ManyToManyField("Author", through="SubmissionAuthor", related_name="submissions")
    status = models.CharField(max_length=40, default="uploaded", db_index=True)
    author_contact = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        title = self.metadata.get("title_ru") or self.submission_id
        return f"{self.submission_id} — {title}"


class Author(models.Model):
    full_name = models.CharField(max_length=255)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authors",
    )
    email = models.EmailField(blank=True)

    def __str__(self) -> str:
        return self.full_name


class SubmissionAuthor(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="author_links",
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="submission_links",
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.submission_id}: {self.author.full_name}"


class SubmissionFile(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="files")
    file_type = models.CharField(max_length=80)
    path = models.CharField(max_length=600)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["file_type", "-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.submission_id}: {self.file_type}"


class CheckResult(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="checks")
    check_id = models.CharField(max_length=120)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=40, default="completed")
    risk_level = models.CharField(max_length=40, default="low")
    score = models.FloatField(null=True, blank=True)
    summary = models.TextField(blank=True)
    warnings = models.JSONField(default=list, blank=True)
    errors = models.JSONField(default=list, blank=True)
    flagged_fragments = models.JSONField(default=list, blank=True)
    author_comment = models.TextField(blank=True)
    editor_comment = models.TextField(blank=True)
    raw_model_response_path = models.CharField(max_length=600, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.submission_id}: {self.check_id}"


class WorkflowStageResult(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="workflow_results")
    stage_id = models.CharField(max_length=120)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=40, default="success")
    message = models.TextField(blank=True)
    result_json = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-finished_at", "-id"]

    def __str__(self) -> str:
        return f"{self.submission_id}: {self.stage_id}"


class StatusHistory(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=40, blank=True)
    to_status = models.CharField(max_length=40)
    changed_by = models.CharField(max_length=120, default="system")
    changed_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return f"{self.submission_id}: {self.from_status} → {self.to_status}"


class EditorDecision(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="editor_decisions")
    decision = models.CharField(max_length=40)
    editor_name = models.CharField(max_length=160, default="editor")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.submission_id}: {self.decision}"


class EventLog(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.submission_id}: {self.event_type}"
