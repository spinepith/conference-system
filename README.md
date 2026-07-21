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

JSON-файлы являются служебными: они сохраняются для workflow и редактора, но не показываются автору заявки и не включаются в пользовательский ZIP. В `result_package.zip` попадают итоговые `formatted_material.docx`, `formatted_material.pdf` и, при наличии, `author_report.pdf|docx`.

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

## ContentValidation (модуль студента 4)

`src/windows_start.bat` запускает два сервиса под одним супервизором:

- Django: `http://127.0.0.1:8000/`;
- ContentValidation.Api: `http://127.0.0.1:5100/`.

Перед запуском установите .NET 10 SDK и заполните `TOKEN` в корневом `.env`.
После формирования `extracted_metadata.json` workflow вызывает `POST /validate`,
импортирует файлы из `checks/` в базу Django и регистрирует итоговый
`check_result.json` как внутренний файл `check_report`. Автор видит понятные
замечания в интерфейсе, но не получает служебные JSON-файлы.

Для временного запуска без модуля установите:

```env
CONTENT_VALIDATION_ENABLED=0
```
