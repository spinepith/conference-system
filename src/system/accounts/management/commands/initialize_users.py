from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


User = get_user_model()


class Command(BaseCommand):
    help = "Создаёт начальные аккаунты editor и admin, если их ещё нет."

    def handle(self, *args, **options):
        # Ensure groups exist
        editors_group, _ = Group.objects.get_or_create(name="Editors")

        # Create editor user
        editor, created = User.objects.get_or_create(
            username="editor",
            defaults={
                "email": "editor@example.com",
                "first_name": "Редактор",
                "last_name": "Системы",
                "is_staff": False,
                "is_superuser": False,
            }
        )
        if created:
            editor.set_password("editor")
            editor.save()
            editor.groups.add(editors_group)
            self.stdout.write(self.style.SUCCESS(f"✓ Создан аккаунт 'editor' (пароль: editor)"))
        else:
            self.stdout.write(f"• Аккаунт 'editor' уже существует")

        # Create admin user
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "first_name": "Администратор",
                "last_name": "Системы",
                "is_staff": True,
                "is_superuser": True,
            }
        )
        if created:
            admin.set_password("admin")
            admin.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Создан аккаунт 'admin' (пароль: admin)"))
        else:
            self.stdout.write(f"• Аккаунт 'admin' уже существует")
