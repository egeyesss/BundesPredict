from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

# Canonical `teams.name` -> (code, short_name). Codes and short names are the keys the web
# crest set uses, so they have to stay in step with it.
CLUB_IDENTITIES: dict[str, tuple[str, str]] = {
    "Bayern Munich": ("FCB", "Bayern"),
    "Borussia Dortmund": ("BVB", "Dortmund"),
    "Bayer 04 Leverkusen": ("B04", "Leverkusen"),
    "RB Leipzig": ("RBL", "Leipzig"),
    "Eintracht Frankfurt": ("SGE", "Frankfurt"),
    "VfB Stuttgart": ("VFB", "Stuttgart"),
    "SC Freiburg": ("SCF", "Freiburg"),
    "Borussia Mönchengladbach": ("BMG", "Gladbach"),
    "1.FSV Mainz 05": ("M05", "Mainz"),
    "TSG 1899 Hoffenheim": ("TSG", "Hoffenheim"),
    "SV Werder Bremen": ("SVW", "Bremen"),
    "FC Augsburg": ("FCA", "Augsburg"),
    "1.FC Union Berlin": ("FCU", "Union Berlin"),
    "1.FC Köln": ("KOE", "Köln"),
    "Hamburger SV": ("HSV", "Hamburg"),
    "FC Schalke 04": ("S04", "Schalke"),
    "SC Paderborn 07": ("SCP", "Paderborn"),
    "SV 07 Elversberg": ("SVE", "Elversberg"),
}


def fill_team_codes(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    team_model = apps.get_model("football", "Team")
    database = schema_editor.connection.alias
    for name, (code, short_name) in CLUB_IDENTITIES.items():
        team_model.objects.using(database).filter(name=name).update(
            code=code, short_name=short_name
        )


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0003_team_code_and_short_name"),
    ]

    operations = [
        migrations.RunPython(fill_team_codes, reverse_code=migrations.RunPython.noop),
    ]
