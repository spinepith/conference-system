from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from accounts.demo_accounts import ensure_demo_accounts


class Command(BaseCommand):
    help = "Создаёт группы Authors/Editors и локальные демонстрационные аккаунты."

    def handle(self, *args, **options):
        for name in ("Authors", "Editors"):
            _, created = Group.objects.get_or_create(name=name)
            self.stdout.write(f"{name}: {'created' if created else 'exists'}")

        results = ensure_demo_accounts(reset_passwords=True)
        for account, _ in results:
            self.stdout.write(f"{account.role}: {account.username} / {account.password}")
