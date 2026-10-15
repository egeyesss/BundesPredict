from django.db import migrations, models


def retype(sql_type: str) -> str:
    # The stored values are naive UTC, so the instant is the same under either type.
    return (
        f"ALTER TABLE predictions ALTER COLUMN created_at "
        f"TYPE {sql_type} USING created_at AT TIME ZONE 'UTC'"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("predictions", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=retype("timestamp with time zone"),
                    reverse_sql=retype("timestamp without time zone"),
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="prediction",
                    name="created_at",
                    field=models.DateTimeField(
                        db_default=models.Func(function="now", output_field=models.DateTimeField())
                    ),
                ),
            ],
        ),
    ]
