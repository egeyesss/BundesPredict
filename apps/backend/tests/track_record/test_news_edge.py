from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest

from football.models import Fixture, Match, ModelRun, Team
from predictions.models import Prediction
from track_record.news_edge import MIN_CHATS_FOR_RATE, build_news_edge, edge_verdict

pytestmark = pytest.mark.django_db

KICKOFF = datetime(2026, 10, 17, 13, 30, tzinfo=UTC)

Chat = Callable[..., Prediction]


class TestEdgeVerdict:
    def test_ahead_when_the_agent_moved_with_the_market_and_landed_nearer_the_close(self) -> None:
        verdict = edge_verdict(opening=0.66, agent=0.70, closing=0.69)

        assert verdict.ahead is True
        assert verdict.reason == "ahead of the market"

    def test_overshooting_the_close_is_not_ahead(self) -> None:
        verdict = edge_verdict(opening=0.40, agent=0.50, closing=0.43)

        assert verdict.ahead is False
        assert verdict.reason == "overshot the market"

    def test_moving_against_the_market_is_not_ahead(self) -> None:
        verdict = edge_verdict(opening=0.40, agent=0.43, closing=0.38)

        assert verdict.ahead is False
        assert verdict.reason == "market went the other way"

    def test_a_market_that_did_not_move_leaves_nothing_to_be_ahead_of(self) -> None:
        verdict = edge_verdict(opening=0.40, agent=0.45, closing=0.40)

        assert verdict.ahead is False
        assert verdict.reason == "market didn't move"

    def test_an_agent_that_left_the_opening_line_alone_is_not_ahead(self) -> None:
        verdict = edge_verdict(opening=0.40, agent=0.40, closing=0.45)

        assert verdict.ahead is False
        assert verdict.reason == "agent stayed on the opening line"

    def test_landing_as_far_from_the_close_as_the_open_was_is_not_ahead(self) -> None:
        verdict = edge_verdict(opening=0.50, agent=0.70, closing=0.60)

        assert verdict.ahead is False
        assert verdict.reason == "overshot the market"


@pytest.fixture
def chat() -> Chat:
    run = ModelRun.objects.create(
        model_type="dixon_coles",
        version="serve",
        xi=0.0018,
        rho=-0.1,
        home_adv=0.25,
        log_likelihood=-1.0,
        n_matches=100,
    )
    teams = {name: Team.objects.create(name=name) for name in ("Alpha", "Bravo")}
    Fixture.objects.create(
        season="2627", matchday=6, kickoff_utc=KICKOFF, home=teams["Alpha"], away=teams["Bravo"]
    )

    def build(
        *,
        base: tuple[float, float, float] = (0.50, 0.25, 0.25),
        served: tuple[float, float, float] = (0.55, 0.23, 0.22),
        adjustments: list[dict[str, object]] | None = None,
        hours_before: float = 3,
        result: tuple[int, int] | None = None,
        opening_odds: tuple[float, float, float] | None = None,
        closing_odds: tuple[float, float, float] | None = None,
    ) -> Prediction:
        prediction = Prediction.objects.create(
            model_run=run,
            home=teams["Alpha"],
            away=teams["Bravo"],
            match_date=KICKOFF.date(),
            query="Alpha's keeper is out",
            p_home=served[0],
            p_draw=served[1],
            p_away=served[2],
            exp_home_goals=1.5,
            exp_away_goals=1.0,
            base_p_home=base[0],
            base_p_draw=base[1],
            base_p_away=base[2],
            adjustments_json=[{"kind": "absence"}] if adjustments is None else adjustments,
        )
        Prediction.objects.filter(pk=prediction.pk).update(
            created_at=KICKOFF - timedelta(hours=hours_before)
        )
        prediction.refresh_from_db()
        if result is not None and not Match.objects.filter(season="2627").exists():
            odds_o = opening_odds or (None, None, None)
            odds_c = closing_odds or (None, None, None)
            Match.objects.create(
                season="2627",
                date=date(2026, 10, 17),
                home=teams["Alpha"],
                away=teams["Bravo"],
                home_goals=result[0],
                away_goals=result[1],
                ftr="H",
                avg_home=odds_o[0],
                avg_draw=odds_o[1],
                avg_away=odds_o[2],
                avgc_home=odds_c[0],
                avgc_draw=odds_c[1],
                avgc_away=odds_c[2],
            )
        return prediction

    return build


class TestBuildNewsEdge:
    def test_logs_a_chat_that_applied_news_before_kickoff(self, chat: Chat) -> None:
        chat()

        edge = build_news_edge()

        assert edge["n_logged"] == 1
        row = edge["chats"][0]
        assert row["outcome"] == "H"
        assert row["agent"] == pytest.approx(0.55)
        assert row["hours_before_kickoff"] == pytest.approx(3.0)
        assert row["home"]["name"] == "Alpha"
        assert "query" not in row

    def test_the_outcome_is_the_one_the_news_moved_most(self, chat: Chat) -> None:
        chat(base=(0.50, 0.25, 0.25), served=(0.48, 0.24, 0.28))

        assert build_news_edge()["chats"][0]["outcome"] == "A"

    def test_a_plain_question_without_adjustments_is_not_a_news_chat(self, chat: Chat) -> None:
        chat(adjustments=[])

        assert build_news_edge()["n_logged"] == 0

    def test_a_chat_after_kickoff_is_not_logged(self, chat: Chat) -> None:
        chat(hours_before=-1)

        assert build_news_edge()["n_logged"] == 0

    def test_compares_with_the_opening_and_closing_lines_once_the_match_has_odds(
        self, chat: Chat
    ) -> None:
        # De-vigged: opening home 0.50, closing home 0.60 (odds sum their inverses to 1).
        chat(
            served=(0.58, 0.22, 0.20),
            result=(2, 0),
            opening_odds=(2.0, 4.0, 4.0),
            closing_odds=(1 / 0.6, 1 / 0.2, 1 / 0.2),
        )

        row = build_news_edge()["chats"][0]

        assert row["opening"] == pytest.approx(0.50)
        assert row["closing"] == pytest.approx(0.60)
        assert row["ahead"] is True
        assert row["verdict"] == "ahead of the market"

    def test_without_a_closing_line_the_chat_is_listed_but_not_judged(self, chat: Chat) -> None:
        chat(result=(1, 0))

        edge = build_news_edge()

        assert edge["n_logged"] == 1
        assert edge["n_compared"] == 0
        assert edge["chats"][0]["ahead"] is None
        assert edge["chats"][0]["verdict"] == "waiting for the closing line"

    def test_no_rate_before_twenty_compared_chats(self, chat: Chat) -> None:
        for _ in range(MIN_CHATS_FOR_RATE - 1):
            chat(
                served=(0.58, 0.22, 0.20),
                result=(2, 0),
                opening_odds=(2.0, 4.0, 4.0),
                closing_odds=(1 / 0.6, 1 / 0.2, 1 / 0.2),
            )

        edge = build_news_edge()

        assert edge["n_compared"] == MIN_CHATS_FOR_RATE - 1
        assert edge["rate"] is None
        assert edge["minimum_for_rate"] == MIN_CHATS_FOR_RATE

    def test_a_rate_appears_at_twenty_compared_chats(self, chat: Chat) -> None:
        for index in range(MIN_CHATS_FOR_RATE):
            chat(
                served=(0.58, 0.22, 0.20) if index % 2 == 0 else (0.40, 0.30, 0.30),
                result=(2, 0),
                opening_odds=(2.0, 4.0, 4.0),
                closing_odds=(1 / 0.6, 1 / 0.2, 1 / 0.2),
            )

        edge = build_news_edge()

        assert edge["n_ahead"] == MIN_CHATS_FOR_RATE // 2
        assert edge["rate"] == pytest.approx(0.5)
