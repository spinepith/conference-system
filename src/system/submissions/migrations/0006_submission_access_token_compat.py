from __future__ import annotations

import secrets

from django.db import migrations, models

import submissions.models


def ensure_access_token_column(apps, schema_editor):
    """Synchronize Django state with clean and legacy SQLite databases.

    Some databases created by earlier branches already contain a NOT NULL
    ``access_token`` column, while the current branch did not describe it in
    the Django model or migration state. A normal AddField migration would
    fail on those databases with a duplicate-column error.
    """

    connection = schema_editor.connection
    table_name = "submissions_submission"
    quoted_table = schema_editor.quote_name(table_name)
    quoted_token = schema_editor.quote_name("access_token")
    quoted_pk = schema_editor.quote_name("submission_id")

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    if "access_token" not in columns:
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} "
            f"ADD COLUMN {quoted_token} varchar(64) NOT NULL DEFAULT ''"
        )

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {quoted_pk} FROM {quoted_table} "
            f"WHERE {quoted_token} IS NULL OR {quoted_token} = %s",
            [""],
        )
        submission_ids = [row[0] for row in cursor.fetchall()]
        for submission_id in submission_ids:
            cursor.execute(
                f"UPDATE {quoted_table} SET {quoted_token} = %s WHERE {quoted_pk} = %s",
                [secrets.token_urlsafe(32), submission_id],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0005_submission_ownership_and_audit"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_access_token_column,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="submission",
                    name="access_token",
                    field=models.CharField(
                        default=submissions.models.generate_access_token,
                        editable=False,
                        max_length=64,
                    ),
                ),
            ],
        ),
    ]
