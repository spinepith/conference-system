# Новые промпты ContentValidation - ПРАВИЛЬНАЯ ВЕРСИЯ

## ✅ Создано 6 промптов

1. **SemanticQuality.txt** - смысловая проверка (9 критериев)
2. **ThematicMatch.txt** - тематическое соответствие
3. **ScientificStructure.txt** - научная структура
4. **FormulationQuality.txt** - качество формулировок
5. **RestrictedContent.txt** - недопустимое содержание ⚠️ с flagged_fragments
6. **PersonalData.txt** - персональные данные ⚠️ с flagged_fragments

---

## 🎯 Ключевые исправления

### 1. Проблема склеивания комментариев

**Причина:** Код в `FinalResult.cs` (строки 110-111) СПЕЦИАЛЬНО склеивает все комментарии через пробел:
```csharp
AuthorMessage = string.Join(" ", authorMessages),
EditorMessage = string.Join(" ", editorMessages),
```

**Решение:** Промпты теперь требуют КОРОТКИЕ комментарии (1-2 предложения), чтобы после склеивания получался связный текст.

### 2. flagged_fragments в ДВУХ проверках

**Было неправильно:** Я думал, что flagged_fragments заменяет warnings/errors
**Правильно:** flagged_fragments это ДОПОЛНИТЕЛЬНОЕ поле, используется ВМЕСТЕ с warnings/errors

**Используется в:**
- ✅ RestrictedContent.txt - для провокационных фрагментов
- ✅ PersonalData.txt - для персональных данных

**НЕ используется в:**
- ❌ SemanticQuality.txt
- ❌ ThematicMatch.txt
- ❌ ScientificStructure.txt
- ❌ FormulationQuality.txt

### 3. Структура JSON

#### Для проверок 1-4 (без flagged_fragments):
```json
{
  "check_id": "...",
  "title": "...",
  "status": "passed | warning | failed",
  "risk_level": "low | medium | high",
  "score": 0.85,
  "summary": "...",
  "warnings": [...],
  "errors": [...],
  "author_comment": "1-2 предложения",
  "editor_comment": "1-2 предложения"
}
```

#### Для проверок 5-6 (с flagged_fragments):
```json
{
  "check_id": "...",
  "title": "...",
  "status": "passed | warning | failed",
  "risk_level": "low | medium | high",
  "score": 0.85,
  "summary": "...",
  "warnings": [...],
  "errors": [...],
  "flagged_fragments": [
    {
      "fragment": "минимальный фрагмент текста",
      "risk_type": "personal_data | ...",
      "reason": "почему помечен",
      "recommendation": "что сделать"
    }
  ],
  "author_comment": "1-2 предложения",
  "editor_comment": "1-2 предложения"
}
```

### 4. Согласованность status и risk_level

**Жёсткие правила:**
```
status="passed"  → risk_level="low"    ВСЕГДА
status="warning" → risk_level="medium" ВСЕГДА
status="failed"  → risk_level="high"   ВСЕГДА
```

Исключение: PersonalData может иметь status="warning" с risk_level="high" при критических данных (паспорта, СНИЛС).

### 5. Детальные инструкции

Каждый промпт содержит:
- Роль и задачу
- Границы полномочий (НЕ принимает решение)
- Критерии проверки (детально!)
- Правила score с диапазонами
- Правила status и risk_level
- Различие warnings vs errors
- Словарь кодов
- Правила для всех полей
- Формат JSON с примером
- Особые инструкции для каждой проверки

---

## 📊 Основные требования из ТЗ

### Из раздела 12 (смысловая проверка):
- 9 критериев проверки
- JSON с status, risk_level, score, summary, warnings, errors, author_comment, editor_comment

### Из раздела 13 (чувствительные сведения):
- 7 категорий проверки
- JSON с flagged_fragments
- Каждый фрагмент: fragment, risk_type, reason, recommendation

### Общие требования:
- Не принимать окончательное решение
- Формировать рекомендации для редактора
- Быть осторожным в формулировках
- Все поля обязательны (даже пустые массивы)

---

## 🔧 Особенности реализации

### PersonalDataChecker.cs - Hybrid подход
Код использует **regex + LLM**:
1. Regex находит: email, телефоны, паспорта, СНИЛС, ИНН, адреса
2. LLM находит: контекстуальные упоминания ФИО, описания данных
3. Результаты **объединяются** в один список flagged_fragments

### FinalResult.cs - Склеивание комментариев
```csharp
// Строки 81-89: Собирает все комментарии
foreach (var item in results) {
    if (!string.IsNullOrEmpty(item.AuthorComment))
        authorMessages.Add(item.AuthorComment);
    if (!string.IsNullOrEmpty(item.EditorComment))
        editorMessages.Add(item.EditorComment);
}

// Строки 110-111: Склеивает через пробел
AuthorMessage = string.Join(" ", authorMessages),
EditorMessage = string.Join(" ", editorMessages),
```

Поэтому каждый промпт требует КОРОТКИЕ комментарии (1-2 предложения).

---

## 🧪 Как тестировать

```bash
cd src/content-validation

# Компиляция (если нужно)
dotnet build ContentValidation.Cli -c Release

# Тест с новыми промптами
dotnet ContentValidation.Cli/bin/Release/net10.0/ContentValidation.Cli.dll TEST-PERFECT --prompts "Prompts/New"

# Сравнить результат
cat ../../storage/submissions/TEST-PERFECT/check_result.json
```

Ожидаемый результат:
- ✅ Короткие комментарии (не склеенный длинный текст)
- ✅ Согласованность status/risk_level
- ✅ flagged_fragments в RestrictedContent и PersonalData
- ✅ warnings/errors везде присутствуют

---

## 🔄 Как применить

### Вариант 1: Заменить старые промпты
```bash
cd ContentValidation/Prompts
rm SemanticQuality.txt ThematicMatch.txt ScientificStructure.txt FormulationQuality.txt RestrictedContent.txt PersonalData.txt
cp New/*.txt .
```

### Вариант 2: Изменить путь по умолчанию
Измените в коде вызов:
```bash
dotnet ContentValidation.Cli.dll SUB-001 --prompts "Prompts/New"
```

Или в `ContentValidation.cs` измените дефолтный путь.

---

## ⚠️ ВАЖНО

### warnings vs errors vs flagged_fragments

**warnings** = общие замечания, не критичные
**errors** = критические проблемы, блокирующие
**flagged_fragments** = конкретные фрагменты текста для проверки (ТОЛЬКО в RestrictedContent и PersonalData)

Все три поля ВСЕГДА должны быть в JSON (даже если пустые массивы []).

### Короткие комментарии

Каждая проверка добавляет свой комментарий. Система склеивает их в одну строку.

**Плохо:** "Материал изложен грамотно, научный стиль выдержан на высоком уровне. Замечаний по качеству формулировок нет. Рекомендуем продолжить работу в этом направлении."

**Хорошо:** "Стиль изложения соответствует научному. Замечаний нет."

---

## 📝 Что изменилось по сравнению со старыми промптами

### БЫЛО (неправильно):
- ❌ Слишком короткие промпты (недостаточно инструкций)
- ❌ flagged_fragments только в PersonalData
- ❌ Не учитывалось склеивание комментариев
- ❌ Нечёткие критерии score

### СТАЛО (правильно):
- ✅ Детальные промпты с полными инструкциями
- ✅ flagged_fragments в RestrictedContent И PersonalData
- ✅ Требование коротких комментариев (1-2 предложения)
- ✅ Чёткие диапазоны score для каждого уровня
- ✅ Жёсткая согласованность status/risk_level
- ✅ Примеры JSON в каждом промпте

---

**Дата:** 2026-07-18  
**Статус:** ✅ Готово к тестированию и применению
