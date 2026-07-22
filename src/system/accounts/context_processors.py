from django.conf import settings
from django.urls import reverse

from .demo_accounts import configured_demo_accounts
from .permissions import is_administrator, is_author, is_editor


def _cabinet_url(user) -> str:
    if not user or not user.is_authenticated:
        return reverse("accounts:login")
    if is_author(user):
        return reverse("author_dashboard")
    if is_editor(user):
        return reverse("editorial:editor_list")
    if is_administrator(user):
        return reverse("admin_dashboard")
    return reverse("index")


def role_flags(request):
    show_demo_accounts = bool(settings.DEBUG and settings.CREATE_DEMO_ACCOUNTS)
    return {
        "is_author_role": is_author(request.user),
        "is_editor_role": is_editor(request.user),
        "is_admin_role": is_administrator(request.user),
        "cabinet_url": _cabinet_url(request.user),
        "show_demo_accounts": show_demo_accounts,
        "demo_accounts": configured_demo_accounts() if show_demo_accounts else (),
    }
