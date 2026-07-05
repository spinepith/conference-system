from __future__ import annotations

VALID_STATUSES = {
    "draft",
    "uploaded",
    "structure_extracted",
    "formatted",
    "auto_checking",
    "auto_checked",
    "needs_author_review",
    "author_confirmed",
    "needs_revision",
    "editor_review",
    "accepted",
    "rejected",
    "included_in_issue",
    "published",
    "error",
}

# Для MVP оставляем гибкую схему, но запрещаем неизвестные статусы.
# Это позволяет интегрировать разные модули без блокировки проекта.
ALLOWED_TRANSITIONS = {
    "draft": {"uploaded", "error"},
    "uploaded": {"structure_extracted", "formatted", "auto_checking", "needs_revision", "error"},
    "structure_extracted": {"formatted", "auto_checking", "needs_revision", "error"},
    "formatted": {"auto_checking", "auto_checked", "needs_author_review", "error"},
    "auto_checking": {"auto_checked", "needs_revision", "error"},
    "auto_checked": {"needs_author_review", "editor_review", "needs_revision", "error"},
    "needs_author_review": {"author_confirmed", "needs_revision", "error"},
    "author_confirmed": {"editor_review", "needs_revision", "error"},
    "needs_revision": {"uploaded", "structure_extracted", "formatted", "auto_checking", "error"},
    "editor_review": {"accepted", "rejected", "needs_revision", "needs_author_review", "error"},
    "accepted": {"included_in_issue", "published", "error"},
    "rejected": {"needs_revision", "error"},
    "included_in_issue": {"published", "accepted", "error"},
    "published": set(),
    "error": {"uploaded", "structure_extracted", "formatted", "auto_checking", "editor_review"},
}


def validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown submission status: {status}")


def can_transition(from_status: str, to_status: str) -> bool:
    validate_status(from_status)
    validate_status(to_status)
    if from_status == to_status:
        return True
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


def assert_transition(from_status: str, to_status: str) -> None:
    if not can_transition(from_status, to_status):
        raise ValueError(f"Transition {from_status!r} -> {to_status!r} is not allowed")
