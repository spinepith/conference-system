from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_existing_owners(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    Submission = apps.get_model("submissions", "Submission")
    for submission in Submission.objects.filter(owner__isnull=True).iterator():
        contact = submission.author_contact or {}
        email = str(contact.get("email") or "").strip()
        if not email:
            continue
        user = User.objects.filter(email__iexact=email).order_by("pk").first()
        if user:
            submission.owner_id = user.pk
            submission.save(update_fields=["owner"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("submissions", "0004_checkresult_content_validation_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_submissions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="editordecision",
            name="editor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="editor_decisions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="statushistory",
            name="changed_by_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="submission_status_changes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="eventlog",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="submission_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(assign_existing_owners, migrations.RunPython.noop),
    ]
