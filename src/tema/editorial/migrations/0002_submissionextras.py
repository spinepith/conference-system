from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("editorial", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubmissionExtras",
            fields=[
                (
                    "submission",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="editorial_extras",
                        serialize=False,
                        to="submissions.submission",
                    ),
                ),
                ("postponed_at", models.DateTimeField(blank=True, null=True)),
                ("postponed_at_status", models.CharField(blank=True, max_length=40)),
            ],
            options={
                "verbose_name": "Отложенное решение по заявке",
                "verbose_name_plural": "Отложенные решения по заявкам",
            },
        ),
    ]
