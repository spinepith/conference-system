# Модуль 1 — Django-ядро

Модуль хранит заявки, авторов, организации, статусы, файлы и результаты
workflow. Он является главным процессом проекта и загружает общий файл
`conference-system/.env` в `conference_project/settings.py`.

## Интеграция с модулем 2

Путь берётся из корневой переменной:

```env
PATH_MODULE_DOCX_PROCESSING=src/docx_processing
```

Ядро добавляет родительскую папку модуля в `sys.path`, а затем адаптер
`submissions/integrations/docx_stages.py` вызывает публичные функции
`docx_processing.service`.

Модуль 2 не импортирует Django-модели. Преобразование его словарей в модели,
статусы и записи `SubmissionFile` выполняется только адаптером модуля 1.

## Общие ресурсы

```env
PATH_STORAGE=storage
PATH_CONFERENCE_TEMPLATE=templates/conference_template_v1.docx
```

База: `storage/conference.db`.

Файлы заявки: `storage/submissions/<submission_id>/`.

## Запуск

Из корня репозитория откройте:

```text
src/windows_start.bat
```

Ручная проверка:

```powershell
cd src/system
python manage.py check
python manage.py makemigrations --check
python manage.py test
```
