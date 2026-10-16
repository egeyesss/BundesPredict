from __future__ import annotations

from datetime import datetime

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ErrorSerializer, ModelUnavailable

from .models import Fixture, Team
from .repositories import FixtureScope, latest_model_run, upcoming_fixtures
from .serializers import (
    FixtureCardSerializer,
    FixtureDetailSerializer,
    FixtureListQuerySerializer,
    TeamSerializer,
)
from .services import fixture_card, ratings_for, team_payload


class TeamListView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        operation_id="teams_list",
        tags=["football"],
        responses=TeamSerializer(many=True),
        description="Clubs that have a code, and so a crest identity, ordered by name.",
    )
    def get(self, request: Request) -> Response:
        teams = Team.objects.filter(code__isnull=False).order_by("name")
        payload = [team_payload(t) for t in teams]
        return Response(TeamSerializer(payload, many=True).data)  # type: ignore[arg-type]


class FixtureListView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        operation_id="fixtures_list",
        tags=["football"],
        parameters=[FixtureListQuerySerializer],
        responses={
            200: FixtureCardSerializer(many=True),
            400: ErrorSerializer,
            503: ErrorSerializer,
        },
        description=(
            "Fixtures still to be played with the base model's probabilities. Fixtures the "
            "newest model run has no ratings for are left out."
        ),
    )
    def get(self, request: Request) -> Response:
        query = FixtureListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        scope: FixtureScope = query.validated_data["scope"]

        run = latest_model_run()
        if run is None:
            raise ModelUnavailable
        ratings = ratings_for(run)
        now: datetime = timezone.now()
        cards = [
            card
            for fixture in upcoming_fixtures(scope, now)
            if (card := fixture_card(fixture, run, ratings)) is not None
        ]
        return Response(
            FixtureCardSerializer(cards, many=True).data  # type: ignore[arg-type]
        )


class FixtureDetailView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        operation_id="fixtures_retrieve",
        tags=["football"],
        responses={200: FixtureDetailSerializer, 404: ErrorSerializer, 503: ErrorSerializer},
    )
    def get(self, request: Request, id: int) -> Response:
        fixture = get_object_or_404(Fixture.objects.select_related("home", "away"), pk=id)
        run = latest_model_run()
        if run is None:
            raise ModelUnavailable
        card = fixture_card(fixture, run, ratings_for(run), with_markets=True)
        if card is None:
            raise ModelUnavailable
        return Response(FixtureDetailSerializer(card).data)
