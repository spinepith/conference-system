from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0003_author_organization_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="checkresult",
            name="author_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="checkresult",
            name="editor_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="checkresult",
            name="flagged_fragments",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
