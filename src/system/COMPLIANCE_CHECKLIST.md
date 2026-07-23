# Соответствие ТЗ после интеграции

## Студент 1 — ядро

- [x] Django-проект и SQLite
- [x] модели Conference, Issue, Submission, Author, SubmissionFile, CheckResult, WorkflowStageResult, StatusHistory, EditorDecision, EventLog
- [x] создание и просмотр заявок
- [x] статусная машина и история
- [x] файловое хранилище
- [x] workflow engine и plugin registry
- [x] интерфейс автора
- [x] API интеграции

## Студент 2 — DOCX-извлечение

- [x] чтение настоящего DOCX
- [x] извлечение текста и метаданных
- [x] извлечение разделов и литературы
- [x] обработка таблиц и изображений
- [x] `extracted_metadata.json`
- [x] предупреждения вместо падения системы

## Студент 2.доп — шаблонизация

- [x] шаблон `conference_template_v1.docx`
- [x] заполнение машинных полей
- [x] перенос основного текста
- [x] перенос таблиц и изображений
- [x] `formatted_material.docx`
- [x] `formatting_report.json`

## Интеграция

- [x] реальные этапы `extract_metadata` и `format_to_template`
- [x] этапы используют общее Django-ядро
- [x] каждый этап получает актуальные результаты предыдущего
- [x] пути сохраняются в `SubmissionFile`
- [x] статусы меняются `uploaded → structure_extracted → formatted`
- [x] результаты сохраняются в `WorkflowStageResult` и `EventLog`
- [x] интеграционные тесты проходят
