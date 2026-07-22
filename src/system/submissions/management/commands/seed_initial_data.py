from django.core.management.base import BaseCommand

from accounts.demo_accounts import ensure_demo_accounts
from submissions.services import SubmissionService


class Command(BaseCommand):
    help = "Create default conference, issue, organizations and local demo accounts."

    def handle(self, *args, **options):
        SubmissionService().ensure_defaults()
        self.stdout.write(self.style.SUCCESS("Initial conference data prepared."))

        demo_results = ensure_demo_accounts(reset_passwords=True)
        if demo_results:
            self.stdout.write(self.style.SUCCESS("Demo accounts prepared:"))
            for account, _ in demo_results:
                self.stdout.write(f"  {account.role}: {account.username} / {account.password}")
