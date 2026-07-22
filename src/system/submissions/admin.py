from django.contrib import admin

from .models import (
    Author,
    CheckResult,
    Conference,
    EditorDecision,
    EventLog,
    Organization,
    StatusHistory,
    Submission,
    SubmissionFile,
    WorkflowStageResult,
)

# Админка остаётся стандартной: только регистрация моделей без кастомных шаблонов и оформления.
admin.site.register(Conference)
admin.site.register(Organization)
admin.site.register(Submission)
admin.site.register(Author)
admin.site.register(SubmissionFile)
admin.site.register(CheckResult)
admin.site.register(WorkflowStageResult)
admin.site.register(StatusHistory)
admin.site.register(EditorDecision)
admin.site.register(EventLog)
