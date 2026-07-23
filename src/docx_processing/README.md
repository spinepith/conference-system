# Модуль 2 — обработка DOCX

Независимый Python-пакет для двух этапов workflow:

- `extract_metadata` — извлечение структуры и объектов DOCX;
- `format_to_template` — создание материала по общему шаблону.

Публичная точка входа:

```python
from docx_processing.service import extract_metadata, format_to_template
```

При вызове из ядра папка для изображений передаётся явно:

```python
metadata = extract_metadata(
    original_docx_path,
    submission_id=submission_id,
    storage_dir=submissions_storage_dir,
)
```

Поэтому модуль не содержит жёсткой зависимости от структуры Django и не
создаёт `storage` внутри `src/system`.

Workflow-классы Django находятся не здесь, а в:

```text
src/system/submissions/integrations/docx_stages.py
```

Файл `stages.py` оставлен как совместимая точка реэкспорта сервисных функций
и не импортирует несуществующее ядро SQLAlchemy.
