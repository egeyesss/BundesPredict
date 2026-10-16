from django.db import migrations

CREATE_TABLE = """
CREATE TABLE predict_throttle_cache (
    cache_key varchar(255) NOT NULL PRIMARY KEY,
    value text NOT NULL,
    expires timestamp with time zone NOT NULL
);
CREATE INDEX predict_throttle_cache_expires ON predict_throttle_cache (expires);
"""


class Migration(migrations.Migration):
    """The table behind `predictions.throttles.throttle_cache`, shaped like `createcachetable`."""

    dependencies = [
        ("predictions", "0002_naive_utc_columns_to_timestamptz"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_TABLE, reverse_sql="DROP TABLE predict_throttle_cache"),
    ]
