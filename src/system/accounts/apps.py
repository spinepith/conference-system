from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Учётные записи"

    def ready(self):
        # Автоматическая инициализация пользователей при запуске
        from django.core.management import call_command
        try:
            call_command('initialize_roles')
            call_command('initialize_users')
        except Exception:
            # Игнорируем ошибки при миграциях или первом запуске
            pass
