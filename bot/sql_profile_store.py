from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .achievements import unlock_achievements
from .database import DebateArchiveRow, UserProfileRow
from .models import DebateArchiveEntry, DebateMode, DebateSession, TournamentScores
from .profile_store import MAX_HISTORY_ITEMS, ProfileStore
from .storage import SessionStore


class SQLProfileStore:
    """Transactional PostgreSQL/SQLAlchemy profile repository used in v0.4."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        session_store: SessionStore,
    ) -> None:
        self.sessions = sessions
        self.session_store = session_store

    async def record_result(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        scores: TournamentScores,
    ) -> dict[str, Any]:
        active = await self.session_store.get_session(user_id)
        archive = (
            DebateArchiveEntry.from_session(
                active,
                status="completed",
                winner=scores.winner,
                score_total=scores.total,
            )
            if active is not None
            else None
        )
        async with self.sessions.begin() as db:
            row = await self._get_or_create(db, user_id, username, display_name)
            is_new = True
            if archive is not None:
                is_new = await self._upsert_archive(db, user_id, archive)
            profile = self._row_to_profile(row)
            profile["username"] = username
            profile["display_name"] = display_name
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
                totals = dict(profile["score_totals"])
                totals["logic"] = int(totals.get("logic", 0)) + scores.logic
                totals["argumentation"] = int(totals.get("argumentation", 0)) + scores.argumentation
                totals["creativity"] = int(totals.get("creativity", 0)) + scores.creativity
                profile["score_totals"] = totals
                profile["current_streak"] = (
                    int(profile["current_streak"]) + 1 if scores.winner == "user" else 0
                )
                profile["best_streak"] = max(
                    int(profile["best_streak"]),
                    int(profile["current_streak"]),
                )
                profile["xp"] = int(profile["xp"]) + 30 + scores.total
                if scores.winner == "user":
                    profile["xp"] = int(profile["xp"]) + 10
            new_achievements = self._finalize(profile)
            self._apply_profile(row, profile)
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
        async with self.sessions.begin() as db:
            row = await self._get_or_create(db, user_id, username, display_name)
            is_new = await self._upsert_archive(db, user_id, archive)
            profile = self._row_to_profile(row)
            profile["username"] = username
            profile["display_name"] = display_name
            if is_new:
                profile["completed_debates"] = int(profile["completed_debates"]) + 1
                if session.mode is DebateMode.DEBATE:
                    profile["regular_debates"] = int(profile["regular_debates"]) + 1
                profile["xp"] = int(profile["xp"]) + 20 + min(
                    20,
                    session.user_argument_count * 2,
                )
            new_achievements = self._finalize(profile)
            self._apply_profile(row, profile)
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
        async with self.sessions.begin() as db:
            row = await self._get_or_create(db, user_id, username, display_name)
            profile = self._row_to_profile(row)
            profile["username"] = username
            profile["display_name"] = display_name
            profile["fallacy_analyses"] = int(profile["fallacy_analyses"]) + 1
            counts = dict(profile["fallacy_counts"])
            for name in names:
                normalized = " ".join(name.strip().casefold().split())
                if normalized:
                    counts[normalized] = int(counts.get(normalized, 0)) + 1
            profile["fallacy_counts"] = counts
            profile["xp"] = int(profile["xp"]) + 5
            new_achievements = self._finalize(profile)
            self._apply_profile(row, profile)
        result = dict(profile)
        result["new_achievements"] = new_achievements
        return result

    async def history(self, user_id: int, limit: int = 5) -> list[DebateArchiveEntry]:
        count = max(1, min(limit, 10))
        async with self.sessions() as db:
            rows = (
                await db.scalars(
                    select(DebateArchiveRow)
                    .where(DebateArchiveRow.user_id == user_id)
                    .order_by(DebateArchiveRow.ended_at.desc())
                    .limit(count)
                )
            ).all()
        entries: list[DebateArchiveEntry] = []
        for row in rows:
            try:
                entries.append(self._archive_to_model(row))
            except ValueError:
                continue
        return entries

    async def last_debate(self, user_id: int) -> DebateArchiveEntry | None:
        entries = await self.history(user_id, 1)
        return entries[0] if entries else None

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        async with self.sessions() as db:
            row = await db.get(UserProfileRow, user_id)
            return self._row_to_profile(row) if row is not None else None

    async def rank(self, user_id: int) -> int | None:
        entries = await self.top(100_000)
        for position, (key, _) in enumerate(entries, start=1):
            if key == str(user_id):
                return position
        return None

    async def top(self, limit: int = 10) -> list[tuple[str, dict[str, Any]]]:
        async with self.sessions() as db:
            rows = (
                await db.scalars(
                    select(UserProfileRow)
                    .order_by(
                        UserProfileRow.best_total.desc(),
                        UserProfileRow.average_total.desc(),
                        UserProfileRow.xp.desc(),
                    )
                    .limit(max(1, limit))
                )
            ).all()
        return [(str(row.user_id), self._row_to_profile(row)) for row in rows]

    async def delete_user(self, user_id: int) -> bool:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(DebateArchiveRow).where(DebateArchiveRow.user_id == user_id)
            )
            result = await db.execute(
                delete(UserProfileRow).where(UserProfileRow.user_id == user_id)
            )
        return bool(result.rowcount)

    async def import_profile(self, user_id: int, raw: dict[str, Any]) -> bool:
        normalized = ProfileStore._normalize_profile(raw, user_id)
        history = normalized.pop("history", [])
        async with self.sessions.begin() as db:
            existing = await db.get(UserProfileRow, user_id, with_for_update=True)
            created = existing is None
            row = existing or UserProfileRow(user_id=user_id)
            if created:
                db.add(row)
            self._apply_profile(row, normalized)
            for archive_raw in history[-MAX_HISTORY_ITEMS:]:
                try:
                    archive = DebateArchiveEntry.model_validate(archive_raw)
                except ValueError:
                    continue
                await self._upsert_archive(db, user_id, archive)
        return created

    async def _get_or_create(
        self,
        db: AsyncSession,
        user_id: int,
        username: str | None,
        display_name: str,
    ) -> UserProfileRow:
        row = await db.get(UserProfileRow, user_id, with_for_update=True)
        if row is None:
            row = UserProfileRow(
                user_id=user_id,
                username=username,
                display_name=display_name,
            )
            db.add(row)
            await db.flush()
        return row

    async def _upsert_archive(
        self,
        db: AsyncSession,
        user_id: int,
        archive: DebateArchiveEntry,
    ) -> bool:
        row = await db.get(DebateArchiveRow, archive.id, with_for_update=True)
        created = row is None
        if row is None:
            row = DebateArchiveRow(id=archive.id, user_id=user_id)
            db.add(row)
        previous_winner = row.winner if not created else "none"
        previous_score = row.score_total if not created else None
        row.user_id = user_id
        row.topic = archive.topic
        row.mode = archive.mode.value
        row.role = archive.role
        row.difficulty = archive.difficulty.value
        row.status = archive.status
        row.winner = (
            previous_winner
            if archive.winner == "none" and previous_winner in {"user", "bot", "draw"}
            else archive.winner
        )
        row.score_total = previous_score if archive.score_total is None else archive.score_total
        row.user_argument_count = archive.user_argument_count
        row.user_stance = archive.user_stance.value if archive.user_stance else None
        row.started_at = archive.started_at
        row.ended_at = archive.ended_at
        row.fallacies = list(archive.fallacies)
        row.transcript = [message.model_dump(mode="json") for message in archive.transcript]
        await db.flush()
        await self._trim_history(db, user_id)
        return created

    @staticmethod
    async def _trim_history(db: AsyncSession, user_id: int) -> None:
        ids = (
            await db.scalars(
                select(DebateArchiveRow.id)
                .where(DebateArchiveRow.user_id == user_id)
                .order_by(DebateArchiveRow.ended_at.desc())
                .offset(MAX_HISTORY_ITEMS)
            )
        ).all()
        if ids:
            await db.execute(delete(DebateArchiveRow).where(DebateArchiveRow.id.in_(ids)))

    @staticmethod
    def _row_to_profile(row: UserProfileRow) -> dict[str, Any]:
        return ProfileStore._normalize_profile(
            {
                "user_id": row.user_id,
                "username": row.username,
                "display_name": row.display_name,
                "tournaments": row.tournaments,
                "regular_debates": row.regular_debates,
                "completed_debates": row.completed_debates,
                "wins": row.wins,
                "draws": row.draws,
                "losses": row.losses,
                "best_total": row.best_total,
                "average_total": row.average_total,
                "last_scores": row.last_scores or {},
                "score_totals": row.score_totals or {},
                "xp": row.xp,
                "level": row.level,
                "current_streak": row.current_streak,
                "best_streak": row.best_streak,
                "fallacy_analyses": row.fallacy_analyses,
                "fallacy_counts": row.fallacy_counts or {},
                "achievements": row.achievements or [],
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            },
            row.user_id,
        )

    @staticmethod
    def _apply_profile(row: UserProfileRow, profile: dict[str, Any]) -> None:
        row.username = profile.get("username")
        row.display_name = str(profile.get("display_name") or "Пользователь")
        row.tournaments = int(profile.get("tournaments", 0))
        row.regular_debates = int(profile.get("regular_debates", 0))
        row.completed_debates = int(profile.get("completed_debates", 0))
        row.wins = int(profile.get("wins", 0))
        row.draws = int(profile.get("draws", 0))
        row.losses = int(profile.get("losses", 0))
        row.best_total = int(profile.get("best_total", 0))
        row.average_total = float(profile.get("average_total", 0))
        row.last_scores = dict(profile.get("last_scores", {}))
        row.score_totals = dict(profile.get("score_totals", {}))
        row.xp = int(profile.get("xp", 0))
        row.level = int(profile.get("level", 1))
        row.current_streak = int(profile.get("current_streak", 0))
        row.best_streak = int(profile.get("best_streak", 0))
        row.fallacy_analyses = int(profile.get("fallacy_analyses", 0))
        row.fallacy_counts = dict(profile.get("fallacy_counts", {}))
        row.achievements = list(profile.get("achievements", []))
        row.updated_at = datetime.now(UTC)

    @staticmethod
    def _finalize(profile: dict[str, Any]) -> list[str]:
        profile["level"] = max(1, int(profile.get("xp", 0)) // 100 + 1)
        profile["updated_at"] = datetime.now(UTC).isoformat()
        return unlock_achievements(profile)

    @staticmethod
    def _archive_to_model(row: DebateArchiveRow) -> DebateArchiveEntry:
        return DebateArchiveEntry.model_validate(
            {
                "id": row.id,
                "topic": row.topic,
                "mode": row.mode,
                "role": row.role,
                "difficulty": row.difficulty,
                "status": row.status,
                "winner": row.winner,
                "score_total": row.score_total,
                "user_argument_count": row.user_argument_count,
                "user_stance": row.user_stance,
                "started_at": row.started_at,
                "ended_at": row.ended_at,
                "fallacies": row.fallacies or [],
                "transcript": row.transcript or [],
            }
        )
