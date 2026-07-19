from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0002_author_many_to_many"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="author",
            name="organization",
        ),
        migrations.AddField(
            model_name="author",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="authors",
                to="submissions.organization",
            ),
        ),
    ]
