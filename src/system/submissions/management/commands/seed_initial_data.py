from django.core.management.base import BaseCommand

from submissions.services import SubmissionService


class Command(BaseCommand):
    help = "Create default conference, issue and seed organizations."

    def handle(self, *args, **options):
        SubmissionService().ensure_defaults()
        self.stdout.write(self.style.SUCCESS("Initial conference data prepared."))
