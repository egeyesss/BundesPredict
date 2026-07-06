"""The deterministic engine the agent's tools call into.

This is the boundary the project rules care about: the agent orchestrates the
LLM and calls these methods, but it never does the math itself and never touches
the database except through here. The service owns a fitted
:class:`~bundespredict.model.dixon_coles.TeamRatings` (loaded from a persisted
run — serving never refits) and an optional DB session for the form lookup.

It also remembers the *last* prediction it produced, baseline and adjusted, so
the agent loop can persist exactly what the user was shown without re-deriving it
from the transcript.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from bundespredict.data.fixtures import UpcomingFixture, upcoming_fixtures
from bundespredict.data.form import TeamForm, recent_form
from bundespredict.data.players import find_player, normalize_name
from bundespredict.data.results import ResultRow, latest_result_date, recent_results
from bundespredict.model.adjust import predict_adjusted
from bundespredict.model.dixon_coles import TeamRatings
from bundespredict.model.markets import Markets

from .adjustments import Adjustment
from .players import PlayerInfo, lookup_player, penalty_takers


@dataclass(frozen=True)
class GroundingContext:
    """The temporal facts the system prompt anchors the agent to.

    ``today`` is the date the agent should reason from (the request's
    ``match_date`` when given, else the real today), and ``data_through`` is the
    most recent completed result in the database — together they let the agent
    answer "is the league in season?" instead of claiming it has no calendar.
    """

    today: date
    data_through: date | None


@dataclass(frozen=True)
class PredictionRecord:
    """One fixture's baseline and (optionally) adjusted distributions.

    ``adjusted`` is ``None`` when no context was applied; ``served`` is then just
    the baseline. ``adjustments`` are the ones actually applied (already typed and
    validated), so the audit trail is the real list, not the LLM's prose.
    """

    home: str
    away: str
    baseline: Markets
    adjusted: Markets | None
    adjustments: tuple[Adjustment, ...] = field(default_factory=tuple)

    @property
    def served(self) -> Markets:
        return self.adjusted if self.adjusted is not None else self.baseline


class UnknownTeamError(ValueError):
    """Raised when a fixture names a team the fitted model doesn't know."""


class PredictionService:
    """Stateful façade over the pure engine for the agent's tools.

    Holds the fitted ratings and (optionally) a DB session. ``last_prediction``
    tracks the most recent fixture computed, which is what the loop persists.
    """

    def __init__(
        self,
        ratings: TeamRatings,
        *,
        session: Session | None = None,
        as_of_date: date | None = None,
    ) -> None:
        self.ratings = ratings
        self.session = session
        self.as_of_date = as_of_date
        self._known = set(ratings.teams)
        self.last_prediction: PredictionRecord | None = None

    @property
    def context(self) -> GroundingContext:
        """Today + data freshness for the system prompt (empty without a session)."""
        today = self.as_of_date if self.as_of_date is not None else date.today()
        data_through = latest_result_date(self.session) if self.session is not None else None
        return GroundingContext(today=today, data_through=data_through)

    @property
    def teams(self) -> tuple[str, ...]:
        """Canonical team names the model can predict, sorted."""
        return tuple(sorted(self._known))

    def _require_team(self, name: str) -> None:
        if name not in self._known:
            raise UnknownTeamError(name)

    def predict_match(self, home: str, away: str) -> Markets:
        """Baseline distribution for a fixture; records it as the last prediction."""
        self._require_team(home)
        self._require_team(away)
        baseline = self.ratings.predict(home, away)
        self.last_prediction = PredictionRecord(
            home=home, away=away, baseline=baseline, adjusted=None
        )
        return baseline

    def predict_with_context(
        self, home: str, away: str, adjustments: Sequence[Adjustment]
    ) -> Markets:
        """Adjusted distribution for a fixture; records baseline + adjusted.

        The adjustments are already validated :class:`Adjustment`s; the engine
        clamps and floors their effect. An empty list reproduces the baseline.
        """
        self._require_team(home)
        self._require_team(away)
        baseline = self.ratings.predict(home, away)
        adjusted = predict_adjusted(self.ratings, home, away, [a.as_delta() for a in adjustments])
        self.last_prediction = PredictionRecord(
            home=home,
            away=away,
            baseline=baseline,
            adjusted=adjusted,
            adjustments=tuple(adjustments),
        )
        return adjusted

    def team_form(self, team: str, *, n: int = 5) -> TeamForm:
        """Recent results for a team as of this service's ``as_of_date``."""
        if self.session is None:
            raise RuntimeError("team_form needs a database session")
        return recent_form(self.session, team, as_of_date=self.as_of_date, n=n)

    def lookup_player(self, name: str) -> PlayerInfo | None:
        """Role/importance for a player, or ``None`` if unknown.

        The scraped squad table answers first (any contracted player, with
        market value and snapshot age); the seeded JSON is the fallback when
        there is no session or the table hasn't been ingested yet. Penalty
        duty isn't scraped, so it's merged from the curated seed either way.
        """
        if self.session is not None:
            found = find_player(self.session, name)
            if found is not None:
                return PlayerInfo(
                    name=found.name,
                    team=found.team,
                    role=found.position,
                    is_penalty_taker=normalize_name(found.name) in penalty_takers(),
                    importance=found.importance,
                    market_value_eur=found.market_value_eur,
                    scraped_at=found.scraped_at,
                )
        return lookup_player(name)

    def recent_results(self, *, n: int = 9) -> tuple[ResultRow, ...]:
        """The league's last ``n`` completed matches before ``as_of_date``."""
        if self.session is None:
            raise RuntimeError("recent_results needs a database session")
        return recent_results(self.session, as_of_date=self.as_of_date, n=n)

    def upcoming_fixtures(
        self, *, team: str | None = None, n: int = 9
    ) -> tuple[UpcomingFixture, ...]:
        """Scheduled fixtures from this service's ``today`` on, soonest first.

        Not gated on the fitted ratings: a freshly promoted club has fixtures
        before it has any ratings, and asking about its schedule is legitimate.
        The data layer still rejects names the teams table has never seen.
        """
        if self.session is None:
            raise RuntimeError("upcoming_fixtures needs a database session")
        return upcoming_fixtures(self.session, team=team, on_or_after=self.context.today, n=n)
