# Conference System

Учебный репозиторий автоматизированной системы научной конференции.

## Структура

```text
conference-system/
├── .env.example
├── src/
│   ├── windows_start.bat       единый запуск Windows
│   ├── system/                 модуль 1: Django-ядро и workflow
│   ├── docx_processing/        модуль 2: извлечение и форматирование DOCX
│   ├── content-validation/
│   └── tema/
├── storage/                    общая БД, заявки, изображения и отчёты
└── templates/                  общие шаблоны конференции
```

Модуль `system` является главным: при запуске он читает корневой `.env`,
добавляет родительскую папку `docx_processing` в Python path и подключает
модуль 2 через адаптер:

```text
src/system/submissions/integrations/docx_stages.py
```

Сам `docx_processing` не зависит от Django и предоставляет публичные функции
из `docx_processing.service`.

## Быстрый запуск на Windows

Откройте файл:

```text
src/windows_start.bat
```

Скрипт:

1. создаёт корневой `.env` из `.env.example`;
2. создаёт `.venv` в корне проекта;
3. устанавливает зависимости модуля 1 и модуля 2;
4. применяет миграции;
5. создаёт начальные данные;
6. проверяет настройки и запускает `http://127.0.0.1:8000/`.

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

## Общий `.env`

Относительные пути считаются от корня `conference-system`:

```env
PATH_STORAGE=storage
PATH_LOGS=storage/logs
PATH_TEMPLATES=templates
PATH_CONFERENCE_TEMPLATE=templates/conference_template_v1.docx
PATH_MODULE_DOCX_PROCESSING=src/docx_processing
PATH_MODULE_SYSTEM=src/system
```

На другом компьютере пути менять не требуется, если структура репозитория
сохранена.

## Проверка модулей 1 и 2

```powershell
cd src/system
python manage.py check
python manage.py makemigrations --check
python manage.py test
```

После загрузки DOCX и запуска workflow должны появиться:

```text
storage/submissions/<submission_id>/original.docx
storage/submissions/<submission_id>/extracted_metadata.json
storage/submissions/<submission_id>/formatted_material.docx
storage/submissions/<submission_id>/formatting_report.json
```

Изображения из исходного документа сохраняются в той же заявке, в папке
`images`, а не внутри `src/system`.
