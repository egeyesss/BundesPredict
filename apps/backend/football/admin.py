from __future__ import annotations

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from .models import Fixture, Match, ModelRun, Player, SquadValue, Team, TeamAlias, TeamParam


class ReadOnlyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """For tables the fit and the agent write; the admin only inspects them."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False


class TeamAliasInline(admin.TabularInline):  # type: ignore[type-arg]
    model = TeamAlias
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "code", "short_name", "tm_id")
    search_fields = ("name", "code", "short_name", "aliases__alias")
    inlines = [TeamAliasInline]


@admin.register(TeamAlias)
class TeamAliasAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("alias", "source", "team")
    list_filter = ("source",)
    search_fields = ("alias", "team__name")
    list_select_related = ("team",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("date", "season", "home", "away", "home_goals", "away_goals")
    list_filter = ("season",)
    list_select_related = ("home", "away")
    date_hierarchy = "date"


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("kickoff_utc", "season", "matchday", "home", "away")
    list_filter = ("season", "matchday")
    list_select_related = ("home", "away")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "team", "position", "market_value_eur", "scraped_at")
    list_filter = ("team",)
    search_fields = ("name",)
    list_select_related = ("team",)


@admin.register(SquadValue)
class SquadValueAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("season", "team", "value_eur", "scraped_at")
    list_filter = ("season",)
    list_select_related = ("team",)


@admin.register(ModelRun)
class ModelRunAdmin(ReadOnlyAdmin):
    list_display = ("id", "trained_at", "model_type", "as_of_date", "version", "n_matches")
    list_filter = ("model_type",)
    ordering = ("-trained_at", "-id")


@admin.register(TeamParam)
class TeamParamAdmin(ReadOnlyAdmin):
    list_display = ("model_run", "team", "attack", "defense")
    list_filter = ("model_run",)
    list_select_related = ("model_run", "team")
