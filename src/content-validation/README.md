<div align="center">

# ContentValidation

</div>

Выполняет 6 автоматических проверок параллельно:

1. Тематическое соответствие - соответствие теме конференции
2. Смысловая проверка - логическая связность и научная ценность
3. Научная структура - наличие всех необходимых элементов научной работы
4. Качество формулировок - ясность изложения
5. Персональные данные (гибрид: regex + LLM) - email, телефоны, паспорта, СНИЛС, ИНН, адреса
6. Недопустимое содержание - опасные призывы, дискриминация

<br>

## **Быстрый старт**
### 1. Компиляция
```bash
cd src/content-validation/ContentValidation.Cli
dotnet build -c Release
```

### 2. Настройка .env
Создайте `.env` в корне проекта:
```env
TOKEN=your-gemini-api-key
PATH_STORAGE=C:\path\to\storage
```

### 3. Запуск
```bash
cd src/content-validation
dotnet ContentValidation.Cli/bin/Release/net10.0/ContentValidation.Cli.dll SUB-2026-Q1-00001
```

<br>

## **Структура данных**
### Вход:
```
storage/submissions/{submission_id}/
└── extracted_metadata.json
```

### Выход:
```
storage/submissions/{submission_id}/
├── checks/                     ← Результаты каждой проверки
├── check_result.json           ← Итоговый отчёт
└── logs/                       ← Логи выполнения
    ├── llm_calls.log           ← Raw запросы/ответы LLM
    ├── validation.log          ← Ход выполнения
    └── errors.log              ← Только ошибки
```

<br>

## **Интеграция**
### Вход:
- `submission_id` (строка)

### Выход:
- Код возврата: `0` = успех, `1` = ошибка
- Файлы результатов в `storage/submissions/{id}/`

### Python пример:
```python
import subprocess
import json

result = subprocess.run([
    "dotnet",
    "path/to/ContentValidation.Cli.dll",
    submission_id
], capture_output=True, text=True, timeout=300)

if result.returncode != 0:
    raise Exception(f"Ошибка: {result.stderr}")

# Читаем результат
with open(f"storage/submissions/{submission_id}/check_result.json") as f:
    data = json.load(f)
    
if data["overall_status"] == "failed":
    update_status("needs_revision")
elif data["overall_status"] == "needs_attention":
    update_status("needs_author_review")
else:
    update_status("auto_checked")
```

<br>

## **Параметры**
```bash
dotnet ContentValidation.Cli.dll <submission_id> [опции]
```

### Опции:
- `--api-key <ключ>` - API ключ (по умолчанию из TOKEN)
- `--storage <путь>` - Путь к storage (по умолчанию из PATH_STORAGE)
- `--prompts <путь>` - Путь к промптам (по умолчанию: Prompts)
- `--model <модель>` - Модель Gemini (по умолчанию: gemini-3.1-flash-lite)

### Примеры:
```bash
# Базовый
dotnet ContentValidation.Cli.dll SUB-2026-Q1-00001

# С другой моделью
dotnet ContentValidation.Cli.dll SUB-2026-Q1-00001 --model gemini-1.5-pro
```

<br>

## **Формат результата**
### check_result.json:
```json
{
  "submission_id": "SUB-2026-Q1-00001",
  "overall_status": "needs_attention",
  "overall_risk_level": "medium",
  "checks": [
    {
      "check_id": "semantic_quality_check",
      "title": "Смысловая проверка материала",
      "status": "passed",
      "risk_level": "low",
      "summary": "Описание"
    },
    {
      "check_id": "personal_data_check",
      "title": "Проверка персональных и чувствительных данных",
      "status": "passed",
      "risk_level": "low",
      "summary": "Описание"
    },
  ]
}
```

### Возможные статусы:
- `passed` - проверка пройдена
- `warning` - есть замечания
- `failed` - серьёзные проблемы
- `error` - техническая ошибка

### Уровни риска:
- `low`, `medium`, `high`

<br>

## **Тестовые данные**
В `ContentValidation.TestConsole/Tests` есть 9 тестовых материалов:

| ID | Что проверяет | Ожидаемый результат |
|----|---------------|---------------------|
| TEST-PERFECT | Идеальный материал | passed/low |
| TEST-PERSONAL-DATA | 7 типов персональных данных | failed/high |
| TEST-BAD-001 | Бессвязный текст | failed/high |
| TEST-OFF-TOPIC | Не соответствует теме | needs_attention/high |
| TEST-MEDIUM-001 | Нет аннотации | needs_attention/medium |

Подробнее: `ContentValidation.TestConsole/README.md`

<br>

## **Структура проекта**
```
ContentValidation/              ← Библиотека классов
├── Checkers/                   ← 6 типов проверок
├── Core/                       ← LLM
├── Models/                     ← Модели данных
├── Prompts/                    ← Промпты для LLM
└── Services/                   ← Вспомогательные методы

ContentValidation.Cli/          ← CLI для интеграции (ТОЧКА ВХОДА)
└── Program.cs

ContentValidation.TestConsole/  ← Консоль для тестов
└── Program.cs
```

<br>

## **Требования**
- .NET 10 SDK
- Google Gemini API key
## Запуск вместе с Django

В интегрированном проекте API не нужно запускать вручную. Корневой
`src/windows_start.bat` вызывает `src/system/scripts/run_services.py`, который:

1. запускает `ContentValidation.Api` через `dotnet run`;
2. ждёт успешный ответ `GET /health`;
3. запускает Django;
4. останавливает принадлежащий ему процесс API после остановки Django.

Django вызывает:

```http
POST http://127.0.0.1:5100/validate
Content-Type: application/json

{"submissionId":"SUB-2026-Q1-00001"}
```

После ответа Django импортирует `checks/*.json` в таблицу `CheckResult`, а
`check_result.json` регистрирует как внутренний файл `check_report`.
