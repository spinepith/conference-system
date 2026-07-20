# Модуль студента 3: PDF, редактор и выпуски

Модуль подключён к Django-ядру из `src/system` и реализует разделы 22, 25 и 26 ТЗ.

## Структура

- `pdf_export/` — DOCX → PDF через LibreOffice headless.
- `result_export/` — `result_manifest.json` и `result_package.zip`.
- `editorial/` — Django-приложение редакторской панели и управления выпусками.
- `issue_builder/` — группировка по секциям, PDF-сборник и статическая страница архива.
- интеграционный этап ядра: `src/system/submissions/integrations/pdf_stages.py`.

## Workflow

`extract_metadata → format_to_template → export_pdf_and_package`

Этап студента 3 получает `formatted_material.docx`, создаёт в папке заявки:

- `formatted_material.pdf`;
- `result_manifest.json`;
- `result_package.zip`.

Пути регистрируются в `SubmissionFile`, поэтому PDF и ZIP доступны в интерфейсе автора и редактора.

## LibreOffice

Установите LibreOffice. Обычно `soffice` определяется через PATH. Для Windows можно указать в корневом `.env`:

```env
SOFFICE_BIN_PATH=C:/Program Files/LibreOffice/program/soffice.exe
```

При отсутствии LibreOffice этап возвращает понятную структурированную ошибку и не приводит к аварийному завершению Django.

## Интерфейсы

- `/editor/` — список заявок с фильтрами и поиском;
- `/editor/<submission_id>/` — карточка, проверки, файлы, история и решения;
- `/editor/issues/` — создание и список выпусков;
- `/editor/issues/<issue_id>/` — состав выпуска и сборка;
- `/archive/` — публичный архив выпусков.

## Выпуски

Принятый материал переводится в `included_in_issue`, группируется по `metadata.section` и включается в PDF-сборник. Сборник содержит титульную часть, информацию о конференции, оргкомитет, содержание, разделители секций, материалы, номера страниц и выходные данные.

## Проверка

Из `src/system`:

```bash
python manage.py migrate
python manage.py check
python manage.py test
```
