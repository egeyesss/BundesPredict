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

from bundespredict.data.form import TeamForm, recent_form
from bundespredict.model.adjust import predict_adjusted
from bundespredict.model.dixon_coles import TeamRatings
from bundespredict.model.markets import Markets

from .adjustments import Adjustment
from .players import PlayerInfo, lookup_player


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
        """Role/importance for a seeded player, or ``None`` if unknown."""
        return lookup_player(name)
