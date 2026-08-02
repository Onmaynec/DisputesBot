from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .league_models import DEFAULT_PLACEMENT_GAMES
from .pvp_models import PvPQueueEntry, PvPQueueMode


@dataclass(frozen=True, slots=True)
class RankedMatchmakingPolicy:
    base_elo_gap: int = 100
    elo_gap_step: int = 50
    expand_interval_seconds: int = 300
    max_elo_gap: int = 400
    placement_games: int = DEFAULT_PLACEMENT_GAMES

    def __post_init__(self) -> None:
        if self.base_elo_gap <= 0:
            raise ValueError("base_elo_gap must be positive")
        if self.elo_gap_step <= 0:
            raise ValueError("elo_gap_step must be positive")
        if self.expand_interval_seconds <= 0:
            raise ValueError("expand_interval_seconds must be positive")
        if self.max_elo_gap < self.base_elo_gap:
            raise ValueError("max_elo_gap must be at least base_elo_gap")
        if self.placement_games < 0:
            raise ValueError("placement_games must not be negative")

    def search_gap(
        self,
        entry: PvPQueueEntry,
        *,
        now: datetime | None = None,
    ) -> int:
        reference = now or datetime.now(UTC)
        queued_at = self._as_utc(entry.queued_at)
        waited_seconds = max(0, int((reference - queued_at).total_seconds()))
        expansions = waited_seconds // self.expand_interval_seconds
        return min(
            self.max_elo_gap,
            self.base_elo_gap + expansions * self.elo_gap_step,
        )

    def compatible(
        self,
        first: PvPQueueEntry,
        second: PvPQueueEntry,
        *,
        now: datetime | None = None,
    ) -> bool:
        if first.mode is not second.mode:
            return False
        if first.mode is PvPQueueMode.OPEN:
            return True
        if self.is_placement(first) != self.is_placement(second):
            return False
        accepted_gap = max(
            self.search_gap(first, now=now),
            self.search_gap(second, now=now),
        )
        return abs(first.rating - second.rating) <= accepted_gap

    def candidate_key(
        self,
        entrant: PvPQueueEntry,
        candidate: PvPQueueEntry,
    ) -> tuple[int, datetime, int]:
        return (
            abs(entrant.rating - candidate.rating),
            self._as_utc(candidate.queued_at),
            candidate.participant.user_id,
        )

    def is_placement(self, entry: PvPQueueEntry) -> bool:
        return entry.games < self.placement_games

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
