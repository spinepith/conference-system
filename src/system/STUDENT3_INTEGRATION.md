# Интеграция модуля студента 3

## Раздел 22: PDF и пакет файлов

В workflow добавлен этап `export_pdf_and_package` после `format_to_template`.
Он использует `src/tema/result_export/service.py`, создаёт PDF, manifest и ZIP,
а затем регистрирует их в `SubmissionFile`.

Создаваемые типы файлов:

- `formatted_pdf`;
- `result_manifest`;
- `result_package`.

PDF и ZIP доступны на странице автора и в редакторской карточке.

## Раздел 25: редактор

Django-приложение `tema.editorial` подключено в `INSTALLED_APPS` и URL проекта.
Реализованы список с фильтрами, карточка, проверки, файлы, полная история и
решения редактора. Решение сохраняется в `EditorDecision`, а изменение статуса —
в `StatusHistory` и `EventLog`.

## Раздел 26: выпуски

Модель `Issue` ядра дополнена OneToOne-моделью `IssueExtras`. Реализованы создание
выпуска, включение/исключение заявок, группировка по секциям, PDF-сборник,
статическая HTML-страница и публикация материалов.

Миграция: `tema/editorial/migrations/0001_initial.py`.

## Проверка

```bash
cd src/system
python manage.py check
python manage.py makemigrations --check
python manage.py test
python manage.py create_test_issue
```
