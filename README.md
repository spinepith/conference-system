# Система управления научной конференцией

Автоматизированная система приёма, проверки, оформления и публикации материалов постоянно действующей научной конференции по искусственному интеллекту.

## Реализованная функциональность

Система обеспечивает полный цикл обработки материалов конференции:

- **Приём материалов** — загрузка DOCX-файлов авторами через веб-интерфейс
- **Извлечение структуры** — автоматический парсинг названия, авторов, аннотации, ключевых слов, текста и списка литературы
- **Приведение к шаблону** — автоматическое форматирование материала по единому шаблону конференции
- **Автоматические проверки** — 6 типов проверок с использованием LLM (тематическое соответствие, смысловая связность, научная структура, качество формулировок, персональные данные, недопустимое содержание)
- **PDF-экспорт** — конвертация в PDF через LibreOffice
- **Редакторская панель** — просмотр заявок, результатов проверок, принятие решений
- **Управление выпусками** — создание квартальных выпусков, группировка по секциям
- **Сборка сборника** — автоматическая генерация PDF-сборника выпуска с оглавлением
- **Публичный архив** — веб-страница со списком выпусков и материалов
- **Авторизация и роли** — разделение прав авторов и редакторов

## Архитектура

Система состоит из 4 независимых модулей:

```
conference-system/
├── src/
│   ├── system/                    # Модуль 1: Django-ядро, workflow, база данных
│   ├── docx_processing/           # Модуль 2: DOCX-извлечение и форматирование (Python)
│   ├── tema/                      # Модуль 3: PDF-экспорт, редактор, выпуски (Python)
│   └── content-validation/        # Модуль 4: Автоматические проверки (C# .NET 10)
└── storage/
    ├── submissions/               # Файлы материалов
    ├── issues/                    # Сборники выпусков
    └── templates/                 # DOCX-шаблон конференции
```

## Workflow обработки материала

```
Загрузка DOCX автором
↓
Извлечение структуры (extract_metadata)
↓
Приведение к шаблону (format_to_template)
↓
Автоматические проверки (content_validation)
↓
Экспорт PDF и упаковка (export_pdf_and_package)
↓
Согласование автором
↓
Проверка редактором
↓
Включение в выпуск
↓
Сборка PDF-сборника
↓
Публикация в архиве
```

## Быстрый запуск (Windows)

### Требования

- Python 3.11+
- .NET 10 SDK
- LibreOffice (для PDF-экспорта)
- Google Gemini API key

### Автоматический запуск

**Важно:** Перед первым запуском отредактируйте файл `.env` и укажите ваш Google Gemini API key в поле `API_KEY=`.

```cmd
src\windows_start.bat
```

Скрипт автоматически:
- Создаёт `.env` из `.env.example` (если отсутствует)
- Создаёт виртуальное окружение Python
- Устанавливает зависимости
- Применяет миграции базы данных
- Запускает ContentValidation.Api (порт 5100)
- Запускает Django (порт 8000)

После запуска откройте браузер: **http://127.0.0.1:8000/**

**Примечание:** Если у вас не установлен LibreOffice или вы хотите временно отключить автоматические проверки, установите в `.env`:
```env
CONTENT_VALIDATION_ENABLED=0
```

### Ручной запуск

```bash
# Настройка окружения
cp .env.example .env
# Отредактируйте .env и укажите API_KEY

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate

# Установка зависимостей
cd src/system
pip install -r requirements.txt

# Инициализация базы данных
python manage.py migrate
python manage.py initialize_roles

# Запуск
cd ..
python system/scripts/run_services.py
```

## Настройка

Создайте файл `.env` в корне проекта (используйте `.env.example` как образец):

```env
# API ключ для Gemini
API_KEY=your-gemini-api-key-here
LLM_MODEL=gemini-3.1-flash-lite

# Автоматические проверки
CONTENT_VALIDATION_ENABLED=1
CONTENT_VALIDATION_API_URL=http://127.0.0.1:5100
CONTENT_VALIDATION_TIMEOUT=360

# Django
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=dev-only-conference-system-secret-key
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# Пути (относительно корня репозитория)
PATH_STORAGE=storage
PATH_LOGS=storage/logs
PATH_TEMPLATES=storage/templates
PATH_CONFERENCE_TEMPLATE=storage/templates/conference_template_v1.docx
PATH_MODULE_CONTENT_VALIDATION=src/content-validation
PATH_MODULE_DOCX_PROCESSING=src/docx_processing
PATH_MODULE_SYSTEM=src/system
PATH_MODULE_TEMA=src/tema
ISSUES_STORAGE_DIR=storage/issues

# LibreOffice (для PDF)
SOFFICE_BIN_PATH=C:/Program Files/LibreOffice/program/soffice.exe

# Токен для внутренних API
INTERNAL_API_TOKEN=change-me-to-a-long-random-token
```

## Интерфейсы

- **http://127.0.0.1:8000/** — главная страница, подача материалов
- **http://127.0.0.1:8000/editor/** — редакторская панель
- **http://127.0.0.1:8000/editor/issues/** — управление выпусками
- **http://127.0.0.1:8000/archive/** — публичный архив выпусков
- **http://127.0.0.1:8000/admin/** — Django Admin
- **http://127.0.0.1:8000/api/** — REST API
- **http://127.0.0.1:5100/** — ContentValidation API (внутренний)

## Создание пользователей

### Создание редактора

```bash
cd src/system
python manage.py createsuperuser
```

Суперпользователь автоматически получает права редактора.

### Регистрация автора

Откройте **http://127.0.0.1:8000/accounts/register/** и зарегистрируйтесь через веб-форму. Новые пользователи автоматически попадают в группу "Authors".

## Тестирование

```bash
cd src/system

# Проверка конфигурации
python manage.py check

# Проверка миграций
python manage.py makemigrations --check

# Запуск тестов
python manage.py test

# Создание тестового выпуска (5 материалов)
python manage.py create_test_issue
```

## Структура файлов материала

После обработки в папке материала создаются:

```
storage/submissions/SUB-2026-Q1-00001/
├── original.docx                  # Исходный файл автора
├── extracted_metadata.json        # Извлечённая структура
├── formatted_material.docx        # Оформленный по шаблону
├── formatted_material.pdf         # PDF версия
├── formatting_report.json         # Отчёт форматирования
├── result_manifest.json           # Манифест итоговых файлов
├── result_package.zip             # ZIP для автора (DOCX + PDF)
├── checks/                        # Результаты каждой проверки (6 файлов)
├── check_result.json              # Итоговый отчёт проверок
└── logs/                          # Логи валидации
    ├── llm_calls.log
    ├── validation.log
    └── errors.log
```

## Статусы материала

- `draft` — черновик
- `uploaded` — файл загружен
- `structure_extracted` — структура извлечена
- `formatted` — приведён к шаблону
- `auto_checking` — выполняются проверки
- `auto_checked` — проверки завершены
- `needs_author_review` — требует согласования автора
- `author_confirmed` — автор подтвердил
- `needs_revision` — требуется доработка
- `editor_review` — на проверке редактора
- `accepted` — принято
- `rejected` — отклонено
- `included_in_issue` — включено в выпуск
- `published` — опубликовано
- `error` — ошибка обработки

## Автоматические проверки

Модуль ContentValidation выполняет 6 параллельных проверок:

1. **Тематическое соответствие** — соответствие теме конференции по ИИ
2. **Смысловая проверка** — логическая связность, цель, методы, результаты
3. **Научная структура** — наличие всех необходимых элементов научной работы
4. **Качество формулировок** — ясность и точность изложения
5. **Персональные данные** — email, телефоны, паспорта, СНИЛС, адреса (гибрид regex + LLM)
6. **Недопустимое содержание** — призывы к незаконным действиям, дискриминация

Результаты проверок носят рекомендательный характер. Финальное решение о публикации принимает редактор.

## Отключение автоматических проверок

Для временного отключения модуля ContentValidation установите в `.env`:

```env
CONTENT_VALIDATION_ENABLED=0
```

## Структура модулей

### Модуль 1: Django-ядро (src/system)

- Управление заявками, авторами, организациями
- Workflow и машина состояний
- Хранение файлов и результатов проверок
- История действий
- REST API
- Авторизация и разделение ролей

### Модуль 2: DOCX-обработка (src/docx_processing)

- Извлечение структуры DOCX (название, авторы, аннотация, ключевые слова, текст, список литературы)
- Приведение к единому шаблону конференции
- Перенос таблиц и изображений

### Модуль 3: PDF и редактор (src/tema)

- Конвертация DOCX в PDF через LibreOffice
- Упаковка результатов для автора
- Редакторская панель
- Управление выпусками
- Сборка PDF-сборника
- Публичный архив

### Модуль 4: Автоматические проверки (src/content-validation)

- 6 типов проверок на базе LLM
- HTTP API для интеграции
- CLI для ручного запуска
- Структурированные результаты в JSON

## Известные ограничения

- Поддерживается только формат DOCX (не .doc)
- Не обрабатываются сканированные PDF
- Требуется установка LibreOffice для PDF-экспорта
- Автоматические проверки требуют Google Gemini API key
- Сложные Word-формулы могут обрабатываться некорректно

## Разработка и расширение

Система спроектирована модульно. Для добавления нового этапа обработки:

1. Создайте класс-наследник `BaseWorkflowStage` в `src/system/submissions/base_stage.py`
2. Зарегистрируйте этап в `plugin_registry.py`
3. Добавьте вызов в `workflow.py`

Каждый модуль имеет собственный README с подробной документацией:

- `src/system/README.md`
- `src/docx_processing/README.md`
- `src/tema/README.md`
- `src/content-validation/README.md`

## Технологический стек

**Backend:**
- Python 3.11+
- Django 5.0+
- SQLite
- python-docx, docxtpl (DOCX)
- reportlab, pypdf (PDF)
- LibreOffice (конвертация)

**Автоматические проверки:**
- C# .NET 10
- Google Gemini API
- System.CommandLine

**Frontend:**
- Django Templates
- Базовый CSS
