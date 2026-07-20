from __future__ import annotations

from django.db import models

from submissions.models import Issue


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
