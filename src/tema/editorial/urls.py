from django.urls import path

from . import views

app_name = "editorial"

urlpatterns = [
    path("editor/", views.editor_list, name="editor_list"),
    path("editor/<str:submission_id>/", views.editor_card, name="editor_card"),
    path("editor/<str:submission_id>/decision/", views.editor_decision, name="editor_decision"),
    path("editor/<str:submission_id>/run-pdf-export/", views.run_pdf_export, name="run_pdf_export"),
    path("download/<str:submission_id>/<str:file_type>/", views.download_by_type, name="download_by_type"),
    path("editor/issues/", views.issue_list, name="issue_list"),
    path("editor/issues/<str:issue_id>/", views.issue_detail, name="issue_detail"),
    path("editor/issues/<str:issue_id>/submissions/<str:submission_id>/add/", views.issue_add_submission, name="issue_add_submission"),
    path("editor/issues/<str:issue_id>/submissions/<str:submission_id>/remove/", views.issue_remove_submission, name="issue_remove_submission"),
    path("editor/issues/<str:issue_id>/build/", views.issue_build, name="issue_build"),
    path("issues/<str:issue_id>/download/collection/", views.download_collection, name="download_collection"),
    path("archive/", views.archive_index, name="archive_index"),
    path("archive/<str:issue_id>/", views.archive_issue, name="archive_issue"),
]
