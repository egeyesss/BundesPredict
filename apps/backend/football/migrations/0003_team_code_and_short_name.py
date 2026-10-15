from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0002_naive_utc_columns_to_timestamptz"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="code",
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
        migrations.AddField(
            model_name="team",
            name="short_name",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddConstraint(
            model_name="team",
            constraint=models.UniqueConstraint(fields=("code",), name="teams_code_key"),
        ),
    ]
