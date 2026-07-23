"""Compatibility facade. Django integration lives in tema.editorial.services."""

from tema.editorial.services import (
    add_submission,
    build_issue_collection,
    create_issue,
    issue_to_dict,
    list_candidate_submissions,
    list_included_submissions,
    list_issues_summary,
    remove_submission,
)

__all__ = [
    "add_submission",
    "build_issue_collection",
    "create_issue",
    "issue_to_dict",
    "list_candidate_submissions",
    "list_included_submissions",
    "list_issues_summary",
    "remove_submission",
]
