from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("submissions", "0003_author_organization_fk"),
    ]

    operations = [
        migrations.CreateModel(
            name="IssueExtras",
            fields=[
                (
                    "issue",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="extras",
                        serialize=False,
                        to="submissions.issue",
                    ),
                ),
                ("files", models.JSONField(blank=True, default=dict)),
                ("org_committee", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(default="draft", max_length=40)),
                ("published_at", models.DateField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Дополнительные данные выпуска",
                "verbose_name_plural": "Дополнительные данные выпусков",
            },
        ),
    ]
