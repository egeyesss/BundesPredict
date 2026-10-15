from __future__ import annotations

import pytest
from django.contrib import admin
from django.db.models import Model
from django.test import Client
from django.urls import reverse

from football.models import Fixture, Match, ModelRun, Player, SquadValue, Team, TeamAlias, TeamParam
from predictions.models import Prediction

pytestmark = pytest.mark.django_db

EDITABLE_MODELS = [Team, TeamAlias, Match, Fixture, Player, SquadValue]
READ_ONLY_MODELS = [ModelRun, TeamParam, Prediction]


def changelist_url(model: type[Model]) -> str:
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")


@pytest.mark.parametrize("model", EDITABLE_MODELS + READ_ONLY_MODELS)
def test_every_model_is_registered_and_its_changelist_renders(
    admin_client: Client, model: type[Model]
) -> None:
    assert admin.site.is_registered(model)

    assert admin_client.get(changelist_url(model)).status_code == 200


@pytest.mark.parametrize("model", READ_ONLY_MODELS)
def test_ml_tables_cannot_be_added_changed_or_deleted_from_the_admin(
    admin_client: Client, model: type[Model]
) -> None:
    model_admin = admin.site._registry[model]
    request = admin_client.get(changelist_url(model)).wsgi_request

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)

    add_url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_add")
    assert admin_client.get(add_url).status_code == 403


@pytest.mark.parametrize("model", EDITABLE_MODELS)
def test_reference_data_can_be_edited_by_a_superuser(
    admin_client: Client, model: type[Model]
) -> None:
    model_admin = admin.site._registry[model]
    request = admin_client.get(changelist_url(model)).wsgi_request

    assert model_admin.has_change_permission(request)


def test_team_changelist_searches_by_name_code_and_alias(admin_client: Client) -> None:
    team = Team.objects.create(name="Bayern Munich", code="FCB", short_name="Bayern")
    TeamAlias.objects.create(alias="FC Bayern München", source="openligadb", team=team)
    Team.objects.create(name="RB Leipzig", code="RBL")

    for term in ("Munich", "FCB", "München"):
        response = admin_client.get(changelist_url(Team), {"q": term})
        assert [t.name for t in response.context["cl"].result_list] == ["Bayern Munich"]
