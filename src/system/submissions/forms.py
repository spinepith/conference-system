from django import forms
import json


class SubmissionForm(forms.Form):
    full_name = forms.CharField(label="ФИО контактного автора", max_length=255)
    email = forms.EmailField(label="E-mail")
    organization = forms.CharField(label="Организация", max_length=400)
    title_ru = forms.CharField(label="Название материала", max_length=400)
    section = forms.CharField(label="Секция конференции", max_length=255, required=False)
    authors_json = forms.CharField(widget=forms.HiddenInput(), required=False)
    supervisor = forms.CharField(label="Научный руководитель", max_length=255, required=False)
    abstract_ru = forms.CharField(label="Аннотация", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    keywords_ru = forms.CharField(label="Ключевые слова", required=False)
    docx_file = forms.FileField(label="Файл DOCX")

    def clean_docx_file(self):
        file = self.cleaned_data["docx_file"]
        if not file.name.lower().endswith(".docx"):
            raise forms.ValidationError("Можно загрузить только файл в формате DOCX.")
        return file

    def clean_authors_json(self):
        value = self.cleaned_data.get("authors_json", "")
        if not value:
            return []
        try:
            data = json.loads(value)
            if not isinstance(data, list):
                raise ValueError
            return data
        except Exception:
            raise forms.ValidationError("Некорректный список авторов.")
