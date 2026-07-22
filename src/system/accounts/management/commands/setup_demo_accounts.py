from django.core.management.base import BaseCommand

from accounts.demo_accounts import ensure_demo_accounts


class Command(BaseCommand):
    help = "Создаёт или сбрасывает демонстрационные аккаунты автора, редактора и администратора."

    def handle(self, *args, **options):
        results = ensure_demo_accounts(reset_passwords=True)
        if not results:
            self.stdout.write(self.style.WARNING("CREATE_DEMO_ACCOUNTS выключен — аккаунты не созданы."))
            return

        self.stdout.write(self.style.SUCCESS("Демонстрационные аккаунты готовы:"))
        for account, created in results:
            state = "создан" if created else "обновлён"
            self.stdout.write(
                f"  {account.role}: {account.username} / {account.password} ({state})"
            )
        self.stdout.write(
            self.style.WARNING(
                "Эти данные предназначены только для локальной демонстрации. "
                "Перед публикацией отключите CREATE_DEMO_ACCOUNTS."
            )
        )
