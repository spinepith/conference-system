from __future__ import annotations

from django.db import models

from submissions.models import Issue, Submission


class IssueExtras(models.Model):
    issue = models.OneToOneField(
        Issue,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="extras",
    )
    files = models.JSONField(default=dict, blank=True)
    org_committee = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=40, default="draft")
    published_at = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Дополнительные данные выпуска"
        verbose_name_plural = "Дополнительные данные выпусков"

    def __str__(self) -> str:
        return f"Дополнительные данные выпуска {self.issue_id}"


class SubmissionExtras(models.Model):

    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="editorial_extras",
    )
    postponed_at = models.DateTimeField(null=True, blank=True)
    postponed_at_status = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = "Отложенное решение по заявке"
        verbose_name_plural = "Отложенные решения по заявкам"

    def __str__(self) -> str:
        return f"Доп. данные заявки {self.submission_id}"

    @property
    def is_postponed_for_current_status(self) -> bool:
        return bool(self.postponed_at) and self.postponed_at_status == self.submission.status