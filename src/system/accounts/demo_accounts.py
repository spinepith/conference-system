from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .permissions import AUTHORS_GROUP, EDITORS_GROUP


@dataclass(frozen=True)
class DemoAccount:
    role: str
    username: str
    password: str
    full_name: str
    email: str


def configured_demo_accounts() -> tuple[DemoAccount, ...]:
    return (
        DemoAccount(
            role="Автор",
            username=settings.DEMO_AUTHOR_USERNAME,
            password=settings.DEMO_AUTHOR_USERNAME,
            full_name="Демонстрационный автор",
            email="author@example.local",
        ),
        DemoAccount(
            role="Редактор",
            username=settings.DEMO_EDITOR_USERNAME,
            password=settings.DEMO_EDITOR_USERNAME,
            full_name="Демонстрационный редактор",
            email="editor@example.local",
        ),
        DemoAccount(
            role="Администратор",
            username=settings.DEMO_ADMIN_USERNAME,
            password=settings.DEMO_ADMIN_USERNAME,
            full_name="Демонстрационный администратор",
            email="admin@example.local",
        ),
    )


def ensure_demo_accounts(*, reset_passwords: bool = True) -> list[tuple[DemoAccount, bool]]:
    """Create predictable local demo users and assign exactly one primary role.

    The helper is enabled only when CREATE_DEMO_ACCOUNTS is true. It is intended
    for the student MVP and local demonstrations, not for a public deployment.
    """
    if not settings.CREATE_DEMO_ACCOUNTS:
        return []

    authors_group, _ = Group.objects.get_or_create(name=AUTHORS_GROUP)
    editors_group, _ = Group.objects.get_or_create(name=EDITORS_GROUP)
    user_model = get_user_model()
    results: list[tuple[DemoAccount, bool]] = []

    for account in configured_demo_accounts():
        user, created = user_model.objects.get_or_create(
            username=account.username,
            defaults={
                "first_name": account.full_name,
                "email": account.email,
            },
        )
        user.first_name = account.full_name
        user.email = account.email
        user.is_active = True
        user.is_staff = account.role == "Администратор"
        user.is_superuser = account.role == "Администратор"
        if created or reset_passwords:
            user.set_password(account.password)
        user.save()

        user.groups.remove(authors_group, editors_group)
        if account.role == "Автор":
            user.groups.add(authors_group)
        elif account.role == "Редактор":
            user.groups.add(editors_group)

        results.append((account, created))

    return results
