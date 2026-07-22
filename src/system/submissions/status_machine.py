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

ALLOWED_TRANSITIONS = {
    "draft": {"uploaded", "error"},
    "uploaded": {"structure_extracted", "formatted", "auto_checking", "needs_revision", "error"},
    "structure_extracted": {"formatted", "auto_checking", "needs_revision", "error"},
    "formatted": {"auto_checking", "auto_checked", "needs_author_review", "error"},
    "auto_checking": {"auto_checked", "needs_author_review", "editor_review", "error"},
    "auto_checked": {"needs_author_review", "editor_review", "needs_revision", "error"},
    "needs_author_review": {"author_confirmed", "needs_revision", "error"},
    "author_confirmed": {"editor_review", "error"},
    "needs_revision": {
        "uploaded",
        "structure_extracted",
        "formatted",
        "auto_checking",
        "editor_review",
        "accepted",
        "rejected",
        "error",
    },
    "editor_review": {"accepted", "rejected", "needs_revision", "needs_author_review", "error"},
    "accepted": {"included_in_issue", "published", "rejected", "needs_revision", "error"},
    "rejected": {"editor_review", "accepted", "needs_revision", "error"},
    "included_in_issue": {"accepted", "published", "error"},
    "published": {"error"},
    "error": {"uploaded", "needs_revision", "editor_review"},
}


def validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Неизвестный статус заявки: {status}")


def assert_transition(from_status: str, to_status: str) -> None:
    validate_status(to_status)
    if from_status == to_status:
        return
    if to_status == "error":
        return
    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ValueError(f"Переход статуса {from_status} → {to_status} не разрешён")
