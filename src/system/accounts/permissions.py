from __future__ import annotations

from functools import wraps
from typing import Callable

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

AUTHORS_GROUP = "Authors"
EDITORS_GROUP = "Editors"


def is_editor(user) -> bool:
    """Редактором считается только пользователь группы Editors.

    Статус staff/superuser даёт доступ к Django Admin, но не подменяет
    редакторскую роль в пользовательском интерфейсе конференции.
    """
    return bool(
        user
        and user.is_authenticated
        and user.groups.filter(name=EDITORS_GROUP).exists()
    )


def is_administrator(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )


def is_author(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.groups.filter(name=AUTHORS_GROUP).exists()
    )


def can_view_submission(user, submission) -> bool:
    return is_editor(user) or (
        bool(user and user.is_authenticated)
        and submission.owner_id == user.pk
    )


def editor_required(view_func: Callable) -> Callable:
    @login_required
    @wraps(view_func)
    def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not is_editor(request.user):
            raise PermissionDenied("Доступ разрешён только редактору.")
        return view_func(request, *args, **kwargs)

    return wrapped


def author_required(view_func: Callable) -> Callable:
    @login_required
    @wraps(view_func)
    def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not is_author(request.user):
            raise PermissionDenied("Доступ разрешён только автору.")
        return view_func(request, *args, **kwargs)

    return wrapped
