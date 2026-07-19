# Conference System MVP — Django version

Учебный MVP модуля студента 1: ядро системы конференции, база данных, статусы, файлы, история действий, workflow/plugin registry и авторский интерфейс подачи материалов.

## Что изменено по сравнению с FastAPI-версией

Фронтенд перенесён на Django:

- страницы реализованы через Django views и Django templates;
- форма подачи материала реализована через Django Form;
- загрузка DOCX работает через стандартный механизм `request.FILES`;
- база данных работает через Django ORM;
- админка Django оставлена стандартной: без кастомных шаблонов и оформления.

## Стек

- Python 3.11+
- Django 5
- SQLite
- Django ORM
- Django templates
- HTML/CSS/JavaScript

## Структура

```text
conference_system_student1_django/
  manage.py
  conference_project/
    settings.py
    urls.py
  submissions/
    models.py
    forms.py
    views.py
    services.py
    workflow.py
    plugin_registry.py
    base_stage.py
    status_machine.py
    demo_stages.py
    admin.py
    migrations/
  templates/
    base.html
    index.html
    submit.html
    status.html
  static/
    styles.css
  samples/
    organizations.txt
  scripts/
    create_demo_submission.py
  tests.py
  requirements.txt
  COMPLIANCE_CHECKLIST.md
```

## Быстрый запуск Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_initial_data
python manage.py runserver
```

Открыть:

```text
http://127.0.0.1:8000
```

## Быстрый запуск через run.bat

После установки зависимостей:

```powershell
.\run.bat
```

## Админка

Админка стандартная Django:

```text
http://127.0.0.1:8000/admin/
```

Для входа нужно создать суперпользователя:

```powershell
python manage.py createsuperuser
```

Админка не кастомизировалась: нет изменённых шаблонов, тем, CSS или нестандартного интерфейса админки.

## Основные страницы

```text
/                         главная страница и список заявок
/submit/                  форма подачи материала
/status/<submission_id>/  статус и карточка заявки
/admin/                   стандартная админка Django
```

## API

Без Django REST Framework, чтобы не усложнять MVP. Методы возвращают JSON через обычные Django views:

```text
GET  /api/health/
GET  /api/organizations/?q=...&limit=10
GET  /api/submissions/
POST /api/submissions/
GET  /api/submissions/<submission_id>/
PATCH /api/submissions/<submission_id>/status/
POST /api/submissions/<submission_id>/checks/
POST /api/submissions/<submission_id>/events/
POST /api/submissions/<submission_id>/files/
POST /api/submissions/<submission_id>/editor-decision/
POST /api/submissions/<submission_id>/workflow/run/
```

## Организации

При первом запуске через `seed_initial_data` в БД загружается справочник организаций из:

```text
samples/organizations.txt
```

В форме подачи поле «Организация» работает как обычный ввод с красивыми подсказками. Если автор вводит новую организацию, она сохраняется в таблицу `organizations` и дальше появляется в подсказках.

## Основные модели

- `Conference`
- `Issue`
- `Organization`
- `Submission`
- `Author`
- `SubmissionFile`
- `CheckResult`
- `WorkflowStageResult`
- `StatusHistory`
- `EditorDecision`
- `EventLog`

## Workflow и plugin registry

`workflow.py` запускает зарегистрированные этапы обработки заявки.  
`plugin_registry.py` хранит список доступных этапов.  
`base_stage.py` задаёт общий интерфейс этапа обработки.

В MVP есть демонстрационные этапы-заглушки в `demo_stages.py`. Реальные модули других студентов могут быть подключены через registry без переписывания всего проекта.

## Тесты

```powershell
python manage.py test
```

Проверяются:

- загрузка справочника организаций;
- сохранение новой организации;
- создание заявки;
- API списка заявок;
- запуск workflow.

## Что не входит в этот модуль

Полноценная DOCX-обработка, реальное извлечение структуры, PDF-генерация, LLM-проверки и редакторская панель относятся к другим индивидуальным заданиям. В этом модуле подготовлены база, API и точки интеграции для таких модулей.
