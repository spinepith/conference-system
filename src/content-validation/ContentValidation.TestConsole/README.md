<div align="center">

# Тестирование модуля ContentValidation

</div>

Проект содержит 9 тестовых материалов для полной проверки модуля автоматической валидации.


## **Список тестовых материалов**
### ✅  **Должны пройти все проверки**

#### **TEST-PERFECT** 
**Ожидаемый результат:** `overall_status: passed`, `overall_risk: low`

**Характеристики:**
- ✅ Идеальная структура: введение, цель, методика, результаты, выводы
- ✅ Чёткая научная база: Item Response Theory
- ✅ Конкретные данные: 120 студентов, корреляция r=0.91
- ✅ Полные ссылки на литературу (4 источника)
- ✅ Есть ключевые слова (5 шт)
- ✅ Подробная аннотация
- ✅ Математические формулы
- ✅ Таблицы и графики
- ✅ Тема: ИИ в образовании (соответствует конференции)

**Проверяет:** Все 6 проверок должны вернуть `status: passed`

---

#### **TEST-GOOD-001**
**Ожидаемый результат:** `overall_status: passed`, `overall_risk: low`

**Характеристики:**
- ✅ Хорошая структура
- ✅ Чёткая цель работы
- ✅ Описана методика (BERT, 500 текстов)
- ✅ Есть результаты (точность 87%)
- ✅ Корректные ссылки на литературу
- ✅ Ключевые слова присутствуют
- ✅ Аннотация информативна
- ✅ Тема соответствует ИИ

**Проверяет:** Эталонный материал для сравнения

---

### ⚠️ **Предупреждения, но не критично**
#### **TEST-MEDIUM-001**
**Ожидаемый результат:** `overall_status: needs_attention`, `overall_risk: medium`

**Проблемы:**
- ⚠️ Отсутствует аннотация
- ⚠️ Слабое описание методики
- ⚠️ Ссылки на литературу неформальные ("Статья про чат-ботов из интернета")
- ✅ Но есть структура, цель, результаты

**Проверяет:**
- FormulationQuality: warning (неформальные ссылки)
- ScientificStructure: warning (слабая методика)
- SemanticQuality: warning (недостаточно подробно)

---

#### **TEST-MEDIUM-002**
**Ожидаемый результат:** `overall_status: needs_attention`, `overall_risk: medium`

**Проблемы:**
- ⚠️ Хорошая структура и методика
- ⚠️ Есть эксперименты и метрики
- ⚠️ НО: проблема холодного старта упомянута, но не решена
- ⚠️ Недостаточно критического анализа ограничений

**Проверяет:**
- SemanticQuality: warning (недостаточно критического анализа)
- Остальные: passed

---

#### **TEST-NO-KEYWORDS**
**Ожидаемый результат:** `overall_status: needs_attention`, `overall_risk: medium`

**Проблемы:**
- ⚠️ Отсутствуют ключевые слова
- ✅ Всё остальное хорошо: структура, методика, результаты

**Проверяет:**
- FormulationQuality: warning (нет ключевых слов)
- ScientificStructure: warning (неполная структура)

---

#### **TEST-WEAK-STRUCTURE**
**Ожидаемый результат:** `overall_status: needs_attention`, `overall_risk: medium`

**Проблемы:**
- ⚠️ Нет чёткой методики (только "проводили опрос")
- ⚠️ Нет конкретных результатов (только общие фразы)
- ⚠️ Слабые ссылки ("Что-то про нейросети")
- ⚠️ Не соответствует теме конференции (ИИ упоминается поверхностно)

**Проверяет:**
- ThematicMatch: warning (слабая связь с ИИ)
- ScientificStructure: warning (нет методики)
- SemanticQuality: warning (общие фразы)
- FormulationQuality: warning (неточные формулировки)

---

### ❌ **Серьёзные проблемы**
#### **TEST-OFF-TOPIC**
**Ожидаемый результат:** `overall_status: needs_attention`, `overall_risk: high`

**Проблемы:**
- ❌ Тема не соответствует конференции по ИИ (психология подростков)
- ❌ ИИ вообще не упоминается
- ✅ Но структура научная, есть методика и результаты

**Проверяет:**
- ThematicMatch: failed (не соответствует теме ИИ)
- Остальные: passed (с точки зрения структуры всё ок)

---

#### **TEST-PERSONAL-DATA**
**Ожидаемый результат:** `overall_status: failed`, `overall_risk: high`

**Проблемы:**
- ❌ Содержит персональные данные респондентов:
  - ФИО: "Иванов Сергей Петрович"
  - Телефон: +7 920 123-45-67
  - Email: ivanov.s@example.com
  - Паспорт: 4015 №678901
  - Адрес: ул. Советская, д. 15, кв. 23
  - СНИЛС: 123-456-789-01
  - ИНН: 1234567890
- ⚠️ Нет аннотации
- ✅ Структура присутствует

**Проверяет:**
- PersonalData: failed + множество flagged_fragments
- RestrictedContent: warning (содержит чувствительную информацию)
- ScientificStructure: warning (нет аннотации)

---

#### **TEST-BAD-001**
**Ожидаемый результат:** `overall_status: failed`, `overall_risk: high`

**Проблемы:**
- ❌ Нет структуры (нет введения, методики, результатов)
- ❌ Текст состоит из общих фраз без содержания
- ❌ Нет связности между предложениями
- ❌ Нет цели работы
- ❌ Нет научного содержания
- ❌ Пустые поля: organization, abstract, keywords, references

**Проверяет:**
- SemanticQuality: failed (бессвязный текст)
- ScientificStructure: failed (нет структуры)
- FormulationQuality: failed (общие фразы)
- ThematicMatch: warning (нет конкретики по ИИ)

<br>

## **Просмотр результатов**
```bash
# Итоговый отчёт
cat storage/submissions/TEST-PERFECT/check_result.json

# Детали конкретной проверки
cat storage/submissions/TEST-PERFECT/checks/formulation_quality_check.json
cat storage/submissions/TEST-PERFECT/checks/personal_data_check.json
cat storage/submissions/TEST-PERFECT/checks/restricted_content_check.json
cat storage/submissions/TEST-PERFECT/checks/scientific_structure_check.json
cat storage/submissions/TEST-PERFECT/checks/semantic_quality_check.json
cat storage/submissions/TEST-PERFECT/checks/thematic_match_check.json

# Логи
cat storage/submissions/TEST-PERFECT/logs/validation.log
cat storage/submissions/TEST-PERFECT/logs/llm_calls.log
cat storage/submissions/TEST-PERFECT/logs/errors.log
```

### **Ожидаемая статистика**
| Материал | Overall Status | Risk Level | Failed Checks | Warnings |
|----------|---------------|------------|---------------|----------|
| TEST-PERFECT | passed | low | 0 | 0 |
| TEST-GOOD-001 | passed | low | 0 | 0-1 |
| TEST-MEDIUM-001 | needs_attention | medium | 0 | 2-3 |
| TEST-MEDIUM-002 | needs_attention | medium | 0 | 1-2 |
| TEST-NO-KEYWORDS | needs_attention | medium | 0 | 1-2 |
| TEST-WEAK-STRUCTURE | needs_attention | medium | 0 | 3-4 |
| TEST-OFF-TOPIC | needs_attention | high | 1 | 1-2 |
| TEST-PERSONAL-DATA | failed | high | 1-2 | 2-3 |
| TEST-BAD-001 | failed | high | 3-4 | 1-2 |


### **Критерии успешного прохождения**
Модуль работает корректно, если:
1. TEST-PERFECT получает `passed` / `low`
2. TEST-GOOD-001 получает `passed` / `low`
3. TEST-PERSONAL-DATA обнаруживает все 7 персональных данных
4. TEST-BAD-001 получает `failed` / `high` с 3+ ошибками
5. TEST-OFF-TOPIC определяется как не соответствующий теме
6. Все средние тесты получают `needs_attention` / `medium`
7. Логи пишутся в правильные папки
8. Нет падений программы ни на одном тесте

<br>

## **Примечания**
- PersonalData checker использует regex + LLM (гибридный подход)
- Результаты могут незначительно варьироваться из-за вероятностной природы LLM
- Важно проверить, что все flagged_fragments корректно заполнены в TEST-PERSONAL-DATA
