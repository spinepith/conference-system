# Проверка соответствия ТЗ студента 1

## Задание 18. Ядро системы и база данных

| Требование | Реализация |
|---|---|
| Структура проекта | `conference_system/app`, `core`, `submissions`, `author_ui`, `tests`, `samples` |
| Модели данных | `Conference`, `Issue`, `Submission`, `Author`, `SubmissionFile`, `CheckResult`, `WorkflowStageResult`, `StatusHistory`, `EditorDecision`, `EventLog` |
| SQLite-база | `conference_system/app/database.py` |
| Авто-создание БД | `init_db()` вызывается при старте приложения |
| Создание заявки | `SubmissionService.create_submission`, `POST /api/submissions` |
| Обновление статуса | `update_submission_status`, `PATCH /api/submissions/{id}/status` |
| Список заявок | `list_submissions`, `GET /api/submissions` |
| Карточка заявки | `get_submission`, `GET /api/submissions/{id}` |
| Сохранение путей к файлам | `SubmissionFile`, `save_submission_file`, `POST /api/submissions/{id}/files` |
| Результаты проверок | `CheckResult`, `save_check_result`, `POST /api/submissions/{id}/checks` |
| История действий | `StatusHistory`, `EventLog` |
| Workflow service | `core/workflow.py` |
| Plugin registry | `core/plugin_registry.py`, `core/base_stage.py` |
| Тестовые данные | `app/seed.py`, демо создаётся при старте |
| README | `README.md` |
| Тесты | `tests/test_core.py`, `tests/test_workflow.py` |

## Задание 19. Интерфейс автора и загрузка материалов

| Требование | Реализация |
|---|---|
| Главная страница конференции | `/`, `templates/index.html` |
| Страница подачи материала | `/submit`, `templates/submit.html` |
| Форма автора | поля ФИО, email, организация |
| Форма метаданных | название, секция, соавторы, руководитель, аннотация, ключевые слова |
| Загрузка DOCX | `POST /submit`, `POST /api/submissions/{id}/files` |
| Страница статуса заявки | `/status/{submission_id}` |
| Страница замечаний | блок проверок на странице статуса |
| Скачивание DOCX | `/download/{id}/formatted_docx` |
| Скачивание PDF | `/download/{id}/formatted_pdf` |
| Подтверждение итогового варианта | `/status/{id}/confirm` |
| Загрузка исправленной версии | `/status/{id}/revision` |
| Понятные ошибки | проверка DOCX и пользовательские сообщения |
| Скрытие технических логов от автора | интерфейс показывает только статусы и понятные сообщения |

## Проверка

Команда:

```bash
pytest
```

Результат на момент упаковки:

```text
4 passed
```
