"""Models for the tables Alembic created, adopted in place.

Table, column, index and constraint names match the live schema exactly (`migrate
--fake-initial` trusts that), which is why indexes and unique constraints are declared by name
instead of through `db_index` and `unique`.
"""

from __future__ import annotations

from django.db import models

from .fields import DB_NOW, FLOAT_ZERO


class Team(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=None)
    tm_id = models.IntegerField(null=True, blank=True)
    code = models.CharField(max_length=3, null=True, blank=True)
    short_name = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "teams"
        constraints = [
            models.UniqueConstraint(fields=["name"], name="teams_name_key"),
            models.UniqueConstraint(fields=["tm_id"], name="teams_tm_id_key"),
            models.UniqueConstraint(fields=["code"], name="teams_code_key"),
        ]

    def __str__(self) -> str:
        return self.name


class TeamAlias(models.Model):
    id = models.AutoField(primary_key=True)
    alias = models.CharField(max_length=None)
    source = models.CharField(max_length=None)
    team = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="aliases"
    )

    class Meta:
        db_table = "team_aliases"
        constraints = [models.UniqueConstraint(fields=["alias"], name="team_aliases_alias_key")]

    def __str__(self) -> str:
        return self.alias


class Match(models.Model):
    id = models.AutoField(primary_key=True)
    season = models.CharField(max_length=None)
    date = models.DateField()
    home = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="home_matches"
    )
    away = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="away_matches"
    )

    home_goals = models.IntegerField()
    away_goals = models.IntegerField()
    ftr = models.CharField(max_length=None)

    ht_home_goals = models.IntegerField(null=True, blank=True)
    ht_away_goals = models.IntegerField(null=True, blank=True)
    htr = models.CharField(max_length=None, null=True, blank=True)

    home_shots = models.IntegerField(null=True, blank=True)
    away_shots = models.IntegerField(null=True, blank=True)
    home_sot = models.IntegerField(null=True, blank=True)
    away_sot = models.IntegerField(null=True, blank=True)
    home_fouls = models.IntegerField(null=True, blank=True)
    away_fouls = models.IntegerField(null=True, blank=True)
    home_corners = models.IntegerField(null=True, blank=True)
    away_corners = models.IntegerField(null=True, blank=True)
    home_yellows = models.IntegerField(null=True, blank=True)
    away_yellows = models.IntegerField(null=True, blank=True)
    home_reds = models.IntegerField(null=True, blank=True)
    away_reds = models.IntegerField(null=True, blank=True)

    b365_home = models.FloatField(null=True, blank=True)
    b365_draw = models.FloatField(null=True, blank=True)
    b365_away = models.FloatField(null=True, blank=True)
    avg_home = models.FloatField(null=True, blank=True)
    avg_draw = models.FloatField(null=True, blank=True)
    avg_away = models.FloatField(null=True, blank=True)
    b365c_home = models.FloatField(null=True, blank=True)
    b365c_draw = models.FloatField(null=True, blank=True)
    b365c_away = models.FloatField(null=True, blank=True)
    avgc_home = models.FloatField(null=True, blank=True)
    avgc_draw = models.FloatField(null=True, blank=True)
    avgc_away = models.FloatField(null=True, blank=True)

    # Final-match xG. It must never feed a prediction directly; only rolling averages over
    # matches strictly before kickoff may.
    home_xg = models.FloatField(null=True, blank=True)
    away_xg = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "matches"
        verbose_name_plural = "matches"
        indexes = [
            models.Index(fields=["away"], name="ix_matches_away_id"),
            models.Index(fields=["date"], name="ix_matches_date"),
            models.Index(fields=["home"], name="ix_matches_home_id"),
            models.Index(fields=["season"], name="ix_matches_season"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["season", "home", "away"], name="uq_match_season_home_away"
            )
        ]

    def __str__(self) -> str:
        return f"{self.season} {self.date} {self.home_id} v {self.away_id}"


class Fixture(models.Model):
    id = models.AutoField(primary_key=True)
    season = models.CharField(max_length=None)
    matchday = models.IntegerField()
    kickoff_utc = models.DateTimeField()
    home = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="home_fixtures"
    )
    away = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="away_fixtures"
    )

    class Meta:
        db_table = "fixtures"
        indexes = [
            models.Index(fields=["away"], name="ix_fixtures_away_id"),
            models.Index(fields=["home"], name="ix_fixtures_home_id"),
            models.Index(fields=["kickoff_utc"], name="ix_fixtures_kickoff_utc"),
            models.Index(fields=["season"], name="ix_fixtures_season"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["season", "matchday", "home", "away"],
                name="uq_fixture_season_md_home_away",
            )
        ]

    def __str__(self) -> str:
        return f"{self.season} MD{self.matchday} {self.home_id} v {self.away_id}"


class Player(models.Model):
    id = models.AutoField(primary_key=True)
    tm_id = models.IntegerField()
    team = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="players"
    )
    name = models.CharField(max_length=None)
    position = models.CharField(max_length=None)
    market_value_eur = models.BigIntegerField(null=True, blank=True)
    scraped_at = models.DateTimeField()

    class Meta:
        db_table = "players"
        indexes = [
            models.Index(fields=["name"], name="ix_players_name"),
            models.Index(fields=["team"], name="ix_players_team_id"),
        ]
        constraints = [models.UniqueConstraint(fields=["tm_id"], name="players_tm_id_key")]

    def __str__(self) -> str:
        return self.name


class SquadValue(models.Model):
    id = models.AutoField(primary_key=True)
    season = models.CharField(max_length=None)
    team = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="squad_values"
    )
    value_eur = models.BigIntegerField()
    scraped_at = models.DateTimeField()

    class Meta:
        db_table = "squad_values"
        indexes = [
            models.Index(fields=["season"], name="ix_squad_values_season"),
            models.Index(fields=["team"], name="ix_squad_values_team_id"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["season", "team"], name="uq_squad_value_season_team")
        ]

    def __str__(self) -> str:
        return f"{self.season} {self.team_id}"


class ModelRun(models.Model):
    """One fitted model. Serving reads the newest run; training happens offline."""

    id = models.AutoField(primary_key=True)
    trained_at = models.DateTimeField(db_default=DB_NOW)
    model_type = models.CharField(max_length=None)
    as_of_date = models.DateField(null=True, blank=True)
    xi = models.FloatField()
    rho = models.FloatField()
    home_adv = models.FloatField()
    log_likelihood = models.FloatField()
    n_matches = models.IntegerField()
    version = models.CharField(max_length=None, null=True, blank=True)
    notes = models.CharField(max_length=None, null=True, blank=True)
    xg_coef = models.FloatField(db_default=FLOAT_ZERO)

    class Meta:
        db_table = "model_runs"
        indexes = [models.Index(fields=["as_of_date"], name="ix_model_runs_as_of_date")]

    def __str__(self) -> str:
        return f"run {self.pk} ({self.model_type})"


class TeamParam(models.Model):
    id = models.AutoField(primary_key=True)
    model_run = models.ForeignKey(
        ModelRun, on_delete=models.DB_CASCADE, db_index=False, related_name="team_params"
    )
    team = models.ForeignKey(
        Team, on_delete=models.DO_NOTHING, db_index=False, related_name="team_params"
    )
    attack = models.FloatField()
    defense = models.FloatField()

    class Meta:
        db_table = "team_params"
        indexes = [
            models.Index(fields=["model_run"], name="ix_team_params_model_run_id"),
            models.Index(fields=["team"], name="ix_team_params_team_id"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["model_run", "team"], name="uq_team_param_run_team")
        ]

    def __str__(self) -> str:
        return f"run {self.model_run_id} team {self.team_id}"
