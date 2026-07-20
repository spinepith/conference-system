# Интеграция модулей 1 и 2

- Главный модуль: `src/system`.
- Независимый DOCX-модуль: `src/docx_processing`.
- Единый файл настроек: `conference-system/.env`.
- Пример настроек: `conference-system/.env.example`.
- Общая база и файлы: `conference-system/storage`.
- Шаблон: `conference-system/templates/conference_template_v1.docx`.
- Django-адаптер: `src/system/submissions/integrations/docx_stages.py`.
- Второй модуль не импортирует модели Django и работает через функции
  `docx_processing.service`.
- Workflow передаёт второму модулю абсолютный путь к общей папке заявок,
  поэтому изображения не создаются внутри рабочей директории Django.
