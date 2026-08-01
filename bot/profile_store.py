from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Literal

from .achievements import level_from_xp, unlock_achievements
from .models import DebateArchiveEntry, DebateMode, DebateSession, TournamentScores
from .storage import LeaderboardStore, SessionStore

MAX_HISTORY_ITEMS = 30


class ProfileStore(LeaderboardStore):
    """Backward-compatible v0.3 profile and debate-history store."""

    def __init__(self, path: Any, session_store: SessionStore) -> None:
        super().__init__(path)
        self.session_store = session_store

    async def record_result(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        scores: TournamentScores,
    ) -> dict[str, Any]:
        session = await self.session_store.get_session(user_id)
        async with self._lock:
            data = await asyncio.to_thread(self._read)
            profile = self._profile(data, user_id, username, display_name)
            archive = (
                DebateArchiveEntry.from_session(
                    session,
                    status="completed",
                    winner=scores.winner,
                    score_total=scores.total,
                )
                if session is not None
                else None
            )
            is_new = True if archive is None else self._upsert_archive(profile, archive)
            if is_new:
                tournaments = int(profile["tournaments"]) + 1
                previous_total = float(profile["average_total"]) * (tournaments - 1)
                profile["tournaments"] = tournaments
                profile["completed_debates"] = int(profile["completed_debates"]) + 1
                profile["wins"] = int(profile["wins"]) + int(scores.winner == "user")
                profile["draws"] = int(profile["draws"]) + int(scores.winner == "draw")
                profile["losses"] = int(profile["losses"]) + int(scores.winner == "bot")
                profile["best_total"] = max(int(profile["best_total"]), scores.total)
                profile["average_total"] = round(
                    (previous_total + scores.total) / tournaments,
                    2,
                )
                profile["last_scores"] = {
                    "logic": scores.logic,
                    "argumentation": scores.argumentation,
                    "creativity": scores.creativity,
                    "total": scores.total,
                }
                totals = profile["score_totals"]
                totals["logic"] = int(totals["logic"]) + scores.logic
                totals["argumentation"] = int(totals["argumentation"]) + scores.argumentation
                totals["creativity"] = int(totals["creativity"]) + scores.creativity
                profile["current_streak"] = (
                    int(profile["current_streak"]) + 1 if scores.winner == "user" else 0
                )
                profile["best_streak"] = max(
                    int(profile["best_streak"]),
                    int(profile["current_streak"]),
                )
                profile["xp"] = int(profile["xp"]) + 30 + scores.total
                if scores.winner == "user":
                    profile["xp"] += 10
            new_achievements = self._finalize_profile(profile)
            data[str(user_id)] = profile
            await asyncio.to_thread(self._write, data)
            result = dict(profile)
            result["new_achievements"] = new_achievements
            return result

    async def archive_debate(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        session: DebateSession,
        status: Literal["judged", "cancelled", "replaced"],
        winner: Literal["user", "bot", "draw", "none"] = "none",
        score_total: int | None = None,
    ) -> dict[str, Any]:
        archive = DebateArchiveEntry.from_session(
            session,
            status=status,
            winner=winner,
            score_total=score_total,
        )
        session.archive_id = archive.id
        async with self._lock:
            data = await asyncio.to_thread(self._read)
            profile = self._profile(data, user_id, username, display_name)
            is_new = self._upsert_archive(profile, archive)
            if is_new:
                profile["completed_debates"] = int(profile["completed_debates"]) + 1
                if session.mode is DebateMode.DEBATE:
                    profile["regular_debates"] = int(profile["regular_debates"]) + 1
                profile["xp"] = int(profile["xp"]) + 20 + min(
                    20,
                    session.user_argument_count * 2,
                )
            new_achievements = self._finalize_profile(profile)
            data[str(user_id)] = profile
            await asyncio.to_thread(self._write, data)
            result = dict(profile)
            result["new_achievements"] = new_achievements
            return result

    async def record_fallacy_analysis(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        names: list[str],
    ) -> dict[str, Any]:
        async with self._lock:
            data = await asyncio.to_thread(self._read)
            profile = self._profile(data, user_id, username, display_name)
            profile["fallacy_analyses"] = int(profile["fallacy_analyses"]) + 1
            counts = profile["fallacy_counts"]
            for name in names:
                normalized = " ".join(name.strip().casefold().split())
                if normalized:
                    counts[normalized] = int(counts.get(normalized, 0)) + 1
            profile["xp"] = int(profile["xp"]) + 5
            new_achievements = self._finalize_profile(profile)
            data[str(user_id)] = profile
            await asyncio.to_thread(self._write, data)
            result = dict(profile)
            result["new_achievements"] = new_achievements
            return result

    async def history(self, user_id: int, limit: int = 5) -> list[DebateArchiveEntry]:
        async with self._lock:
            data = await asyncio.to_thread(self._read)
        profile = data.get(str(user_id))
        if not isinstance(profile, dict):
            return []
        entries: list[DebateArchiveEntry] = []
        for raw in profile.get("history", [])[-max(1, min(limit, 10)) :]:
            try:
                entries.append(DebateArchiveEntry.model_validate(raw))
            except ValueError:
                continue
        return list(reversed(entries))

    async def last_debate(self, user_id: int) -> DebateArchiveEntry | None:
        entries = await self.history(user_id, limit=1)
        return entries[0] if entries else None

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        async with self._lock:
            data = await asyncio.to_thread(self._read)
        entry = data.get(str(user_id))
        if not isinstance(entry, dict):
            return None
        return dict(self._normalize_profile(entry, user_id))

    async def rank(self, user_id: int) -> int | None:
        entries = await self.top(limit=10_000)
        for position, (key, _) in enumerate(entries, start=1):
            if key == str(user_id):
                return position
        return None

    async def top(self, limit: int = 10) -> list[tuple[str, dict[str, Any]]]:
        async with self._lock:
            data = await asyncio.to_thread(self._read)
        normalized = [
            (key, self._normalize_profile(value, int(key)))
            for key, value in data.items()
            if key.isdigit() and isinstance(value, dict)
        ]
        return sorted(
            normalized,
            key=lambda item: (
                int(item[1].get("best_total", 0)),
                float(item[1].get("average_total", 0)),
                int(item[1].get("xp", 0)),
            ),
            reverse=True,
        )[:limit]

    def _profile(
        self,
        data: dict[str, Any],
        user_id: int,
        username: str | None,
        display_name: str,
    ) -> dict[str, Any]:
        profile = self._normalize_profile(data.get(str(user_id), {}), user_id)
        profile["username"] = username
        profile["display_name"] = display_name
        profile.pop("new_achievements", None)
        return profile

    @staticmethod
    def _normalize_profile(raw: Any, user_id: int) -> dict[str, Any]:
        source = raw if isinstance(raw, dict) else {}
        profile: dict[str, Any] = {
            "user_id": user_id,
            "username": source.get("username"),
            "display_name": source.get("display_name", "Пользователь"),
            "tournaments": int(source.get("tournaments", 0)),
            "regular_debates": int(source.get("regular_debates", 0)),
            "completed_debates": int(
                source.get("completed_debates", source.get("tournaments", 0))
            ),
            "wins": int(source.get("wins", 0)),
            "draws": int(source.get("draws", 0)),
            "losses": int(source.get("losses", 0)),
            "best_total": int(source.get("best_total", 0)),
            "average_total": float(source.get("average_total", 0)),
            "last_scores": dict(source.get("last_scores", {})),
            "score_totals": dict(
                source.get(
                    "score_totals",
                    {"logic": 0, "argumentation": 0, "creativity": 0},
                )
            ),
            "xp": int(source.get("xp", int(source.get("tournaments", 0)) * 30)),
            "level": int(source.get("level", 1)),
            "current_streak": int(source.get("current_streak", 0)),
            "best_streak": int(source.get("best_streak", 0)),
            "fallacy_analyses": int(source.get("fallacy_analyses", 0)),
            "fallacy_counts": dict(source.get("fallacy_counts", {})),
            "achievements": list(source.get("achievements", [])),
            "history": list(source.get("history", []))[-MAX_HISTORY_ITEMS:],
            "updated_at": source.get("updated_at"),
        }
        for key in ("logic", "argumentation", "creativity"):
            profile["score_totals"][key] = int(profile["score_totals"].get(key, 0))
        profile["level"] = level_from_xp(int(profile["xp"]))
        unlock_achievements(profile)
        return profile

    @staticmethod
    def _upsert_archive(profile: dict[str, Any], archive: DebateArchiveEntry) -> bool:
        history = list(profile.get("history", []))
        payload = archive.model_dump(mode="json")
        for index, existing in enumerate(history):
            if isinstance(existing, dict) and existing.get("id") == archive.id:
                previous_winner = existing.get("winner", "none")
                previous_score = existing.get("score_total")
                if archive.winner == "none" and previous_winner in {"user", "bot", "draw"}:
                    payload["winner"] = previous_winner
                if archive.score_total is None and isinstance(previous_score, int):
                    payload["score_total"] = previous_score
                history[index] = payload
                profile["history"] = history[-MAX_HISTORY_ITEMS:]
                return False
        history.append(payload)
        profile["history"] = history[-MAX_HISTORY_ITEMS:]
        return True

    @staticmethod
    def _finalize_profile(profile: dict[str, Any]) -> list[str]:
        profile["level"] = level_from_xp(int(profile["xp"]))
        profile["updated_at"] = datetime.now(UTC).isoformat()
        return unlock_achievements(profile)
