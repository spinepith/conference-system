# Conference System

Учебный репозиторий автоматизированной системы научной конференции.

## Структура

```text
conference-system/
├── .env.example
├── src/
│   ├── windows_start.bat       единый запуск Windows
│   ├── system/                 модуль 1: Django-ядро и workflow
│   ├── docx_processing/        модуль 2: DOCX-извлечение и форматирование
│   ├── tema/                   модуль 3: PDF, редактор, выпуски и архив
│   └── content-validation/
├── storage/
│   ├── submissions/            файлы заявок
│   └── issues/                 сборники и страницы выпусков
└── templates/                  общий DOCX-шаблон конференции
```

## Workflow модулей 1–3

```text
extract_metadata
→ format_to_template
→ export_pdf_and_package
```

После обработки заявки создаются:

```text
original.docx
extracted_metadata.json
formatted_material.docx
formatting_report.json
formatted_material.pdf
result_manifest.json
result_package.zip
```

`check_report.json` и `author_report.pdf|docx` будут автоматически добавлены в пакет после появления результатов следующих модулей.

## Быстрый запуск на Windows

Откройте:

```text
src/windows_start.bat
```

Скрипт создаёт `.env` и `.venv`, устанавливает зависимости, применяет миграции и запускает сайт на `http://127.0.0.1:8000/`.

Для PDF-экспорта должен быть установлен LibreOffice. Обычно `soffice.exe` находится автоматически. Для нестандартной установки укажите в корневом `.env`:

```env
SOFFICE_BIN_PATH=C:/Program Files/LibreOffice/program/soffice.exe
```

## Ручной запуск

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd src/system
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_initial_data
python manage.py check
python manage.py runserver
```

## Интерфейсы

- `/` — интерфейс автора и список заявок;
- `/editor/` — редакторская панель;
- `/editor/issues/` — управление выпусками;
- `/archive/` — архив выпусков;
- `/admin/` — Django Admin;
- `/api/` — API ядра.

## Общий `.env`

Все относительные пути считаются от корня репозитория:

```env
PATH_STORAGE=storage
PATH_LOGS=storage/logs
PATH_TEMPLATES=templates
PATH_CONFERENCE_TEMPLATE=templates/conference_template_v1.docx
PATH_MODULE_DOCX_PROCESSING=src/docx_processing
PATH_MODULE_SYSTEM=src/system
PATH_MODULE_TEMA=src/tema
ISSUES_STORAGE_DIR=storage/issues
SOFFICE_BIN_PATH=
```

## Проверка

```powershell
cd src/system
python manage.py check
python manage.py makemigrations --check
python manage.py test
```

Также доступна команда для критерия ТЗ «тестовый выпуск из 5 материалов»:

```powershell
python manage.py create_test_issue
```

Подробности модуля 3 находятся в `src/tema/README.md`.
