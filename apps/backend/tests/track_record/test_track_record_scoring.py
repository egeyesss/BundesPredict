from __future__ import annotations

import math

import pytest

from track_record.scoring import (
    BASE_RATE,
    Forecast,
    calibration_bins,
    outcome_index,
    score_forecast,
    summarize,
)

# Hand-computed from RPS = 1/2 * [(C1 - E1)^2 + (C2 - E2)^2] over cumulative probabilities.
HOME_CALLED_HOME = Forecast(probs=(0.5, 0.3, 0.2), outcome=0)
AWAY_FAVOURITE_DRAW = Forecast(probs=(0.2, 0.3, 0.5), outcome=1)
HOME_FAVOURITE_AWAY_WIN = Forecast(probs=(0.6, 0.25, 0.15), outcome=2)


class TestOutcomeIndex:
    @pytest.mark.parametrize(
        ("home_goals", "away_goals", "expected"),
        [(2, 1, 0), (0, 0, 1), (3, 3, 1), (0, 4, 2)],
    )
    def test_maps_the_scoreline_to_home_draw_away(
        self, home_goals: int, away_goals: int, expected: int
    ) -> None:
        assert outcome_index(home_goals, away_goals) == expected


class TestScoreForecast:
    def test_home_win_called_at_50_percent(self) -> None:
        score = score_forecast(HOME_CALLED_HOME)

        assert score.rps == pytest.approx(0.5 * (0.5**2 + 0.2**2))  # 0.145
        assert score.log_loss == pytest.approx(-math.log(0.5))
        assert score.hit is True

    def test_draw_when_the_away_side_was_favoured(self) -> None:
        score = score_forecast(AWAY_FAVOURITE_DRAW)

        assert score.rps == pytest.approx(0.5 * (0.2**2 + 0.5**2))  # 0.145
        assert score.log_loss == pytest.approx(-math.log(0.3))
        assert score.hit is False

    def test_away_win_against_a_home_favourite_costs_two_steps(self) -> None:
        score = score_forecast(HOME_FAVOURITE_AWAY_WIN)

        assert score.rps == pytest.approx(0.5 * (0.6**2 + 0.85**2))  # 0.54125
        assert score.log_loss == pytest.approx(-math.log(0.15))
        assert score.hit is False

    def test_a_tie_for_the_top_pick_goes_to_a_team_over_the_draw(self) -> None:
        tied_draw_and_away = Forecast(probs=(0.2, 0.4, 0.4), outcome=2)
        tied_draw_and_home = Forecast(probs=(0.4, 0.4, 0.2), outcome=1)

        assert score_forecast(tied_draw_and_away).hit is True
        assert score_forecast(tied_draw_and_home).hit is False


class TestSummarize:
    def test_averages_the_three_fixtures(self) -> None:
        summary = summarize([HOME_CALLED_HOME, AWAY_FAVOURITE_DRAW, HOME_FAVOURITE_AWAY_WIN])

        assert summary is not None
        assert summary.n_fixtures == 3
        assert summary.rps == pytest.approx((0.145 + 0.145 + 0.54125) / 3)
        expected_log_loss = (-math.log(0.5) - math.log(0.3) - math.log(0.15)) / 3
        assert summary.log_loss == pytest.approx(expected_log_loss)
        assert summary.hit_rate == pytest.approx(1 / 3)

    def test_nothing_to_summarize_gives_none(self) -> None:
        assert summarize([]) is None


class TestBaseRate:
    def test_is_the_long_run_split_and_sums_to_one(self) -> None:
        assert BASE_RATE == (0.44, 0.25, 0.31)
        assert sum(BASE_RATE) == pytest.approx(1.0)

    def test_scores_a_home_win_at_0_2049(self) -> None:
        score = score_forecast(Forecast(probs=BASE_RATE, outcome=0))

        assert score.rps == pytest.approx(0.5 * (0.56**2 + 0.31**2))


class TestCalibrationBins:
    def test_pools_home_draw_and_away_into_tenth_wide_bins(self) -> None:
        bins = calibration_bins([HOME_CALLED_HOME, AWAY_FAVOURITE_DRAW])

        by_lower = {round(b.lower, 1): b for b in bins}
        # Two fixtures give six points; the 0.2 probabilities (away in the first, home in the
        # second) both missed.
        assert sum(b.count for b in bins) == 6
        assert by_lower[0.2].count == 2
        assert by_lower[0.2].predicted_mean == pytest.approx(0.2)
        assert by_lower[0.2].observed_rate == 0.0

    def test_a_bin_reports_how_often_it_happened(self) -> None:
        bins = calibration_bins([HOME_CALLED_HOME, AWAY_FAVOURITE_DRAW])

        by_lower = {round(b.lower, 1): b for b in bins}
        # Both 0.3 predictions (draw in each fixture): one happened (fixture 2 was a draw).
        assert by_lower[0.3].count == 2
        assert by_lower[0.3].observed_rate == pytest.approx(0.5)

    def test_a_probability_of_exactly_one_lands_in_the_top_bin(self) -> None:
        bins = calibration_bins([Forecast(probs=(1.0, 0.0, 0.0), outcome=0)])

        top = [b for b in bins if b.count and b.upper == pytest.approx(1.0)]
        assert top and top[0].predicted_mean == 1.0

    def test_empty_bins_are_dropped(self) -> None:
        bins = calibration_bins([HOME_CALLED_HOME])

        assert all(b.count > 0 for b in bins)
