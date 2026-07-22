from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import AuthorRegistrationForm
from .permissions import AUTHORS_GROUP


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = AuthorRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            authors_group, _ = Group.objects.get_or_create(name=AUTHORS_GROUP)
            user.groups.add(authors_group)
            login(request, user)
            messages.success(request, "Регистрация завершена. Теперь можно подать материал.")
            return redirect("index")
    else:
        form = AuthorRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})
