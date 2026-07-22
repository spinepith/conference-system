from .permissions import is_author, is_editor


def role_flags(request):
    return {
        "is_author_role": is_author(request.user),
        "is_editor_role": is_editor(request.user),
    }
