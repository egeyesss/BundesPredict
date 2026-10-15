from django.db import migrations, models

NAIVE_UTC_COLUMNS = [
    ("fixtures", "kickoff_utc"),
    ("model_runs", "trained_at"),
    ("players", "scraped_at"),
    ("squad_values", "scraped_at"),
]


def retype(sql_type: str) -> str:
    # The stored values are naive UTC, so the instant is the same under either type.
    return "; ".join(
        f"ALTER TABLE {table} ALTER COLUMN {column} "
        f"TYPE {sql_type} USING {column} AT TIME ZONE 'UTC'"
        for table, column in NAIVE_UTC_COLUMNS
    )


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0001_initial"),
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
                    model_name="fixture",
                    name="kickoff_utc",
                    field=models.DateTimeField(),
                ),
                migrations.AlterField(
                    model_name="modelrun",
                    name="trained_at",
                    field=models.DateTimeField(
                        db_default=models.Func(function="now", output_field=models.DateTimeField())
                    ),
                ),
                migrations.AlterField(
                    model_name="player",
                    name="scraped_at",
                    field=models.DateTimeField(),
                ),
                migrations.AlterField(
                    model_name="squadvalue",
                    name="scraped_at",
                    field=models.DateTimeField(),
                ),
            ],
        ),
    ]
