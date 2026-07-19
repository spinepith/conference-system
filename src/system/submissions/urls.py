from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("submit/", views.submit_material, name="submit"),
    path("status/<str:submission_id>/", views.status_page, name="status"),
    path("status/<str:submission_id>/confirm/", views.confirm_submission, name="confirm_submission"),
    path("status/<str:submission_id>/revision/", views.upload_revision, name="upload_revision"),
    path("download/<int:file_id>/", views.download_file, name="download_file"),
    path("api/", views.api_index, name="api_index"),
    path("api/health/", views.api_health, name="api_health"),
    path("api/organizations/", views.api_organizations, name="api_organizations"),
    path("api/submissions/", views.api_submissions, name="api_submissions"),
    path("api/submissions/<str:submission_id>/", views.api_submission_detail, name="api_submission_detail"),
    path("api/submissions/<str:submission_id>/status/", views.api_submission_status, name="api_submission_status"),
    path("api/submissions/<str:submission_id>/checks/", views.api_submission_checks, name="api_submission_checks"),
    path("api/submissions/<str:submission_id>/events/", views.api_submission_events, name="api_submission_events"),
    path("api/submissions/<str:submission_id>/files/", views.api_submission_files, name="api_submission_files"),
    path("api/submissions/<str:submission_id>/editor-decision/", views.api_editor_decision, name="api_editor_decision"),
    path("api/submissions/<str:submission_id>/workflow/run/", views.api_workflow_run, name="api_workflow_run"),
]
