from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta

import pytest
from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from football.models import ModelRun, Team, TeamParam
from predictions.models import Prediction

pytestmark = pytest.mark.django_db

fill_team_codes_migration = importlib.import_module("football.migrations.0004_fill_team_codes")


def make_run(**fields: object) -> ModelRun:
    defaults: dict[str, object] = {
        "model_type": "dixon_coles",
        "xi": 0.0018,
        "rho": -0.1,
        "home_adv": 0.25,
        "log_likelihood": -1000.0,
        "n_matches": 5000,
    }
    return ModelRun.objects.create(**{**defaults, **fields})


def test_database_defaults_fill_trained_at_and_xg_coef() -> None:
    run = make_run()

    run.refresh_from_db()

    assert run.xg_coef == 0.0
    assert abs(timezone.now() - run.trained_at) < timedelta(minutes=1)
    assert run.trained_at.tzinfo is not None


def make_prediction(**fields: object) -> Prediction:
    defaults: dict[str, object] = {
        "model_run": make_run(),
        "home": Team.objects.create(name="Bayern Munich"),
        "away": Team.objects.create(name="RB Leipzig"),
        "p_home": 0.6,
        "p_draw": 0.2,
        "p_away": 0.2,
        "exp_home_goals": 2.1,
        "exp_away_goals": 0.9,
        "base_p_home": 0.55,
        "base_p_draw": 0.25,
        "base_p_away": 0.2,
    }
    return Prediction.objects.create(**{**defaults, **fields})


def test_prediction_gets_a_utc_created_at_and_a_json_typed_column() -> None:
    prediction = make_prediction()

    prediction.refresh_from_db()

    assert prediction.adjustments_json == []
    assert prediction.created_at.tzinfo is not None
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_typeof(adjustments_json)::text FROM predictions")
        assert cursor.fetchone() == ("json",)


@pytest.mark.parametrize(
    "document",
    [
        [],
        [{"factor": "injury", "note": "Müller \u2192 out"}],
        {"b": 1, "a": [None, 2.5]},
        "just a string",
    ],
)
def test_json_column_preserves_any_json_document(document: object) -> None:
    prediction = make_prediction(adjustments_json=document)

    prediction.refresh_from_db()

    assert prediction.adjustments_json == document


def test_deleting_a_model_run_removes_its_team_params_in_the_database() -> None:
    run = make_run()
    team = Team.objects.create(name="Bayern Munich")
    TeamParam.objects.create(model_run=run, team=team, attack=0.4, defense=-0.3)

    run.delete()

    assert TeamParam.objects.count() == 0


def test_a_team_with_params_cannot_be_deleted() -> None:
    run = make_run()
    team = Team.objects.create(name="Bayern Munich")
    TeamParam.objects.create(model_run=run, team=team, attack=0.4, defense=-0.3)

    # Django creates its foreign keys deferred, so the violation only shows at the check.
    with pytest.raises(IntegrityError), transaction.atomic():
        team.delete()
        connection.check_constraints()


def test_team_codes_are_unique_but_many_teams_may_have_none() -> None:
    Team.objects.create(name="Holstein Kiel")
    Team.objects.create(name="Hertha BSC")
    Team.objects.create(name="Bayern Munich", code="FCB")

    with pytest.raises(IntegrityError), transaction.atomic():
        Team.objects.create(name="FC Bayern", code="FCB")


class TestFillTeamCodes:
    def run_migration(self) -> None:
        with connection.schema_editor() as schema_editor:
            fill_team_codes_migration.fill_team_codes(apps, schema_editor)

    def test_sets_code_and_short_name_on_known_clubs_and_leaves_others_alone(self) -> None:
        Team.objects.create(name="1.FSV Mainz 05")
        Team.objects.create(name="Holstein Kiel")

        self.run_migration()

        mainz = Team.objects.get(name="1.FSV Mainz 05")
        kiel = Team.objects.get(name="Holstein Kiel")
        assert (mainz.code, mainz.short_name) == ("M05", "Mainz")
        assert (kiel.code, kiel.short_name) == (None, None)

    def test_is_safe_on_an_empty_database_and_when_run_twice(self) -> None:
        self.run_migration()
        Team.objects.create(name="Bayern Munich")

        self.run_migration()
        self.run_migration()

        assert Team.objects.get(name="Bayern Munich").code == "FCB"

    def test_covers_eighteen_clubs_with_distinct_three_letter_codes(self) -> None:
        identities = fill_team_codes_migration.CLUB_IDENTITIES.values()
        codes = [code for code, _ in identities]

        assert len(codes) == 18
        assert len(set(codes)) == 18
        assert all(len(code) == 3 and code.isupper() for code in codes)


def test_trained_at_written_as_utc_reads_back_as_the_same_instant() -> None:
    moment = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)

    run = make_run(trained_at=moment)
    run.refresh_from_db()

    assert run.trained_at == moment
