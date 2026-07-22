from django.urls import path

from . import views

app_name = "editorial"

urlpatterns = [
    # Static and more specific editor routes must be declared before
    # editor/<submission_id>/, otherwise Django treats "issues" as a
    # submission_id and opens editor_card instead of the issue list.
    path("editor/issues/", views.issue_list, name="issue_list"),
    path("editor/issues/<str:issue_id>/", views.issue_detail, name="issue_detail"),
    path(
        "editor/issues/<str:issue_id>/submissions/<str:submission_id>/add/",
        views.issue_add_submission,
        name="issue_add_submission",
    ),
    path(
        "editor/issues/<str:issue_id>/submissions/<str:submission_id>/remove/",
        views.issue_remove_submission,
        name="issue_remove_submission",
    ),
    path("editor/issues/<str:issue_id>/build/", views.issue_build, name="issue_build"),

    path("editor/", views.editor_list, name="editor_list"),
    path("editor/<str:submission_id>/decision/", views.editor_decision, name="editor_decision"),
    path(
        "editor/<str:submission_id>/run-pdf-export/",
        views.run_pdf_export,
        name="run_pdf_export",
    ),
    path("editor/<str:submission_id>/", views.editor_card, name="editor_card"),

    path(
        "download/<str:submission_id>/<str:file_type>/",
        views.download_by_type,
        name="download_by_type",
    ),
    path(
        "issues/<str:issue_id>/download/collection/",
        views.download_collection,
        name="download_collection",
    ),
    path("archive/materials/<str:submission_id>.pdf", views.public_material_pdf, name="public_material_pdf"),
    path("archive/", views.archive_index, name="archive_index"),
    path("archive/<str:issue_id>/", views.archive_issue, name="archive_issue"),
]
