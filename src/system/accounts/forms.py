from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class AuthorRegistrationForm(UserCreationForm):
    full_name = forms.CharField(label="ФИО", max_length=150)
    email = forms.EmailField(label="E-mail")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "full_name", "email", "password1", "password2")
        labels = {"username": "Логин"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким e-mail уже зарегистрирован.")
        return email

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["full_name"].strip()
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
