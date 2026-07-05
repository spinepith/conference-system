# Conference System — модуль студента 1

Модуль реализует ядро MVP автоматизированной системы управления постоянно действующей научной конференцией и простой интерфейс автора.

## Что реализовано

- SQLite-база данных создаётся автоматически.
- Модели данных: `Conference`, `Issue`, `Submission`, `Author`, `SubmissionFile`, `CheckResult`, `WorkflowStageResult`, `StatusHistory`, `EditorDecision`, `EventLog`.
- Сервис заявок:
  - `create_submission(data)`
  - `get_submission(submission_id)`
  - `list_submissions(issue_id=None)`
  - `update_submission_status(submission_id, status, comment)`
  - `save_check_result(submission_id, check_result)`
  - `add_event(submission_id, event_type, payload)`
  - `save_submission_file(...)`
  - `save_workflow_stage_result(...)`
- Хранение файлов в `storage/submissions/<submission_id>/`.
- История статусов и журнал событий.
- Workflow engine и plugin registry для подключаемых этапов обработки.
- REST API для интеграции с другими студентами.
- Авторский интерфейс:
  - главная страница конференции;
  - форма подачи материала;
  - загрузка DOCX;
  - страница статуса заявки;
  - просмотр замечаний;
  - скачивание файлов;
  - подтверждение итогового варианта;
  - загрузка исправленной версии.
- Тестовые данные и базовые автотесты.

## Быстрый запуск

```bash
python -m venv .venv
source .venv\Scripts\activate
pip install -r requirements.txt
uvicorn conference_system.app.main:app --reload
```

Открыть в браузере:

```text
http://127.0.0.1:8000
```

Документация API:

```text
http://127.0.0.1:8000/docs
```

## Запуск тестов

```bash
pytest
```

## Переменные окружения

Можно переопределить путь к базе и хранилищу:

```bash
export CONFERENCE_DB_URL=sqlite:///./storage/conference.db
export CONFERENCE_STORAGE_DIR=./storage
```

## Основные API-методы

### Создать заявку

```http
POST /api/submissions
```

Минимальный JSON:

```json
{
  "conference_id": "ai_quarterly_conf",
  "issue_id": "2026_q1",
  "author_contact": {
    "full_name": "Иванов Иван Иванович",
    "email": "ivanov@example.com",
    "organization": "ТГТУ"
  },
  "metadata": {
    "title_ru": "Применение ИИ в образовании",
    "authors": [{"full_name": "Иванов И.И.", "organization": "ТГТУ", "email": "ivanov@example.com"}],
    "supervisor": "Петров П.П.",
    "section": "Искусственный интеллект в образовании",
    "keywords_ru": ["ИИ", "образование"],
    "abstract_ru": ""
  }
}
```

### Получить список заявок

```http
GET /api/submissions
GET /api/submissions?issue_id=2026_q1
```

### Получить карточку заявки

```http
GET /api/submissions/{submission_id}
```

### Обновить статус

```http
PATCH /api/submissions/{submission_id}/status
```

```json
{
  "status": "auto_checking",
  "comment": "Запущены автоматические проверки",
  "changed_by": "system"
}
```

### Сохранить результат проверки

```http
POST /api/submissions/{submission_id}/checks
```

### Загрузить файл

```http
POST /api/submissions/{submission_id}/files
```

Форма multipart:

- `file_type`: `original_docx`, `formatted_docx`, `formatted_pdf`, `check_report`, `revision_docx`
- `file`: файл

## Структура хранения файлов

```text
storage/
  conference.db
  submissions/
    SUB-2026-Q1-00001/
      original.docx
      formatted_material.docx
      formatted_material.pdf
      check_report.json
      revisions/
        revision_20260704_153000.docx
```

## Статусы материала

Поддерживаются статусы:

```text
draft
uploaded
structure_extracted
formatted
auto_checking
auto_checked
needs_author_review
author_confirmed
needs_revision
editor_review
accepted
rejected
included_in_issue
published
error
```

Каждая смена статуса записывается в `StatusHistory` и дублируется в журнал событий.

## Как подключать этапы workflow

Каждый этап должен наследоваться от `BaseWorkflowStage`:

```python
from conference_system.core.base_stage import BaseWorkflowStage

class MyStage(BaseWorkflowStage):
    stage_id = "my_stage"
    title = "Мой этап"
    description = "Описание этапа"

    def run(self, submission: dict) -> dict:
        return {
            "status": "success",
            "message": "Этап выполнен",
            "data": {}
        }
```

Регистрация:

```python
from conference_system.core.plugin_registry import registry
registry.register(MyStage())
```

Запуск:

```python
from conference_system.core.workflow import WorkflowEngine
engine = WorkflowEngine()
engine.run_submission("SUB-2026-Q1-00001")
```

## Известные ограничения MVP

- Нет полноценной авторизации автора.
- Нет промышленной почтовой рассылки.
- DOCX не анализируется внутри этого модуля: файл только принимается и сохраняется. Извлечение DOCX выполняет модуль другого студента.
- PDF не генерируется этим модулем: путь к PDF сохраняется после работы модуля PDF-экспорта.

