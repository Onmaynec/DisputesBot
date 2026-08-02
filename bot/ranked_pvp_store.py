from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .matchmaking import RankedMatchmakingPolicy
from .pvp_models import PvPMatch, PvPQueueEntry, PvPQueueMode
from .pvp_store import PairAllowed, PvPBusyError, PvPStore


class RankedPvPStore(PvPStore):
    def __init__(
        self,
        redis: Any,
        *,
        prefix: str = "disputesbot",
        match_ttl_seconds: int = 86_400,
        invitation_ttl_seconds: int = 600,
        queue_ttl_seconds: int = 1_800,
        lock_ttl_seconds: int = 15,
        turn_timeout_seconds: int = 3_600,
        pair_allowed: PairAllowed | None = None,
        ranked_base_elo_gap: int = 100,
        ranked_elo_gap_step: int = 50,
        ranked_expand_interval_seconds: int = 300,
        ranked_max_elo_gap: int = 400,
    ) -> None:
        super().__init__(
            redis,
            prefix=prefix,
            match_ttl_seconds=match_ttl_seconds,
            invitation_ttl_seconds=invitation_ttl_seconds,
            queue_ttl_seconds=queue_ttl_seconds,
            lock_ttl_seconds=lock_ttl_seconds,
            turn_timeout_seconds=turn_timeout_seconds,
            pair_allowed=pair_allowed,
        )
        self.ranked_policy = RankedMatchmakingPolicy(
            base_elo_gap=ranked_base_elo_gap,
            elo_gap_step=ranked_elo_gap_step,
            expand_interval_seconds=ranked_expand_interval_seconds,
            max_elo_gap=ranked_max_elo_gap,
        )

    async def join_queue(self, entry: PvPQueueEntry) -> PvPMatch | None:
        async with self._named_lock("queue") as acquired:
            if not acquired:
                raise PvPBusyError("Matchmaking queue is busy")
            if await self.get_match_for_user(entry.participant.user_id) is not None:
                raise PvPBusyError("User already has an active match")

            queue = await self._load_queue()
            now = datetime.now(UTC)
            minimum_time = now - timedelta(seconds=self.queue_ttl_seconds)
            retained: list[PvPQueueEntry] = []
            eligible: list[PvPQueueEntry] = []

            for item in queue:
                if self._as_utc(item.queued_at) < minimum_time:
                    continue
                if item.participant.user_id == entry.participant.user_id:
                    continue
                if item.season != entry.season:
                    retained.append(item)
                    continue
                if await self.get_match_for_user(item.participant.user_id) is not None:
                    continue
                if not await self._is_pair_allowed(
                    item.participant.user_id,
                    entry.participant.user_id,
                ):
                    retained.append(item)
                    continue
                if not self.ranked_policy.compatible(item, entry, now=now):
                    retained.append(item)
                    continue
                eligible.append(item)

            if eligible:
                if entry.mode is PvPQueueMode.RANKED:
                    selected = min(
                        eligible,
                        key=lambda item: self.ranked_policy.candidate_key(entry, item),
                    )
                else:
                    selected = min(
                        eligible,
                        key=lambda item: (
                            self._as_utc(item.queued_at),
                            item.participant.user_id,
                        ),
                    )
                retained.extend(item for item in eligible if item is not selected)
                await self._save_queue(retained)
                try:
                    return await self.create_match(
                        selected.participant,
                        entry.participant,
                        topic=selected.topic,
                        season=entry.season,
                        rated_hint=True,
                    )
                except PvPBusyError:
                    retained.extend((selected, entry))
                    await self._save_queue(retained)
                    raise

            retained.append(entry)
            await self._save_queue(retained)
            return None

    async def get_queue_entry(self, user_id: int) -> PvPQueueEntry | None:
        minimum_time = datetime.now(UTC) - timedelta(seconds=self.queue_ttl_seconds)
        for entry in await self._load_queue():
            if (
                entry.participant.user_id == user_id
                and self._as_utc(entry.queued_at) >= minimum_time
            ):
                return entry
        return None

    def ranked_search_gap(
        self,
        entry: PvPQueueEntry,
        *,
        now: datetime | None = None,
    ) -> int:
        return self.ranked_policy.search_gap(entry, now=now)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
