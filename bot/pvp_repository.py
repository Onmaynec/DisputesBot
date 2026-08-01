from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPMatchRow, PvPPlayerRow, UserProfileRow
from .elo import calculate_elo
from .pvp_models import PvPJudgement, PvPMatch, PvPMatchHistoryEntry, PvPUser


@dataclass(frozen=True, slots=True)
class PvPRatingView:
    user_id: int
    display_name: str
    username: str | None
    season: str
    rating: int
    games: int
    wins: int
    draws: int
    losses: int


@dataclass(frozen=True, slots=True)
class PvPRecordResult:
    created: bool
    entry: PvPMatchHistoryEntry

    @property
    def pro_delta(self) -> int:
        return self.entry.pro_rating_after - self.entry.pro_rating_before

    @property
    def con_delta(self) -> int:
        return self.entry.con_rating_after - self.entry.con_rating_before


class PvPRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def record_match(
        self,
        match: PvPMatch,
        *,
        judgement: PvPJudgement | None = None,
    ) -> PvPRecordResult:
        if match.outcome not in {"judged", "draw", "forfeit"}:
            raise ValueError("Only completed rated matches can be persisted")
        if match.outcome in {"judged", "draw"} and judgement is None:
            raise ValueError("A judged match requires a structured judgement")
        if judgement is not None and judgement.winner_user_id != match.winner_user_id:
            raise ValueError("Judgement winner does not match completed match state")

        async with self.sessions.begin() as db:
            users = {match.pro.user_id: match.pro, match.con.user_id: match.con}
            for user_id in sorted(users):
                await self._get_or_create_profile(db, users[user_id])

            existing = await db.get(PvPMatchRow, match.match_id, with_for_update=True)
            if existing is not None:
                return PvPRecordResult(False, self._match_to_model(existing))

            pro = await self._get_or_create_player(db, match.pro.user_id, match.season)
            con = await self._get_or_create_player(db, match.con.user_id, match.season)

            if match.winner_user_id is None:
                pro_score = 0.5
            elif match.winner_user_id == match.pro.user_id:
                pro_score = 1.0
            elif match.winner_user_id == match.con.user_id:
                pro_score = 0.0
            else:
                raise ValueError("Winner is not a participant")

            change = calculate_elo(pro.rating, con.rating, pro_score)
            pro_before = pro.rating
            con_before = con.rating
            pro.rating = change.rating_a_after
            con.rating = change.rating_b_after
            self._apply_game_result(pro, pro_score)
            self._apply_game_result(con, 1.0 - pro_score)
            now = datetime.now(UTC)
            pro.updated_at = now
            con.updated_at = now

            row = PvPMatchRow(
                match_id=match.match_id,
                season=match.season,
                topic=match.topic,
                pro_user_id=match.pro.user_id,
                con_user_id=match.con.user_id,
                winner_user_id=match.winner_user_id,
                outcome=match.outcome,
                pro_rating_before=pro_before,
                pro_rating_after=pro.rating,
                con_rating_before=con_before,
                con_rating_after=con.rating,
                pro_scores=(
                    judgement.pro_scores.model_dump(mode="json") if judgement else {}
                ),
                con_scores=(
                    judgement.con_scores.model_dump(mode="json") if judgement else {}
                ),
                reason=match.verdict_reason or "Матч завершён.",
                transcript=[item.model_dump(mode="json") for item in match.arguments],
                started_at=match.started_at,
                ended_at=match.updated_at,
            )
            db.add(row)
            await db.flush()
            entry = self._match_to_model(row)
        return PvPRecordResult(True, entry)

    async def rating(self, user_id: int, season: str) -> PvPRatingView | None:
        async with self.sessions() as db:
            player = await db.get(PvPPlayerRow, {"user_id": user_id, "season": season})
            if player is None:
                return None
            profile = await db.get(UserProfileRow, user_id)
            if profile is None:
                return None
            return self._rating_view(player, profile)

    async def rank(self, user_id: int, season: str) -> int | None:
        entries = await self.top(season, limit=100_000)
        for position, entry in enumerate(entries, start=1):
            if entry.user_id == user_id:
                return position
        return None

    async def top(self, season: str, limit: int = 10) -> list[PvPRatingView]:
        async with self.sessions() as db:
            rows = (
                await db.execute(
                    select(PvPPlayerRow, UserProfileRow)
                    .join(UserProfileRow, UserProfileRow.user_id == PvPPlayerRow.user_id)
                    .where(PvPPlayerRow.season == season)
                    .order_by(
                        PvPPlayerRow.rating.desc(),
                        PvPPlayerRow.games.desc(),
                        PvPPlayerRow.updated_at.asc(),
                    )
                    .limit(max(1, limit))
                )
            ).all()
        return [self._rating_view(player, profile) for player, profile in rows]

    async def delete_user_data(self, user_id: int) -> None:
        async with self.sessions.begin() as db:
            await db.execute(
                delete(PvPMatchRow).where(
                    or_(
                        PvPMatchRow.pro_user_id == user_id,
                        PvPMatchRow.con_user_id == user_id,
                    )
                )
            )
            await db.execute(
                delete(PvPPlayerRow).where(PvPPlayerRow.user_id == user_id)
            )

    async def history(self, user_id: int, limit: int = 5) -> list[PvPMatchHistoryEntry]:
        async with self.sessions() as db:
            rows = (
                await db.scalars(
                    select(PvPMatchRow)
                    .where(
                        or_(
                            PvPMatchRow.pro_user_id == user_id,
                            PvPMatchRow.con_user_id == user_id,
                        )
                    )
                    .order_by(PvPMatchRow.ended_at.desc())
                    .limit(max(1, min(limit, 10)))
                )
            ).all()
        return [self._match_to_model(row) for row in rows]

    @staticmethod
    async def _get_or_create_profile(
        db: AsyncSession,
        user: PvPUser,
    ) -> UserProfileRow:
        row = await db.get(UserProfileRow, user.user_id, with_for_update=True)
        if row is None:
            row = UserProfileRow(
                user_id=user.user_id,
                username=user.username,
                display_name=user.display_name,
            )
            db.add(row)
            await db.flush()
        else:
            row.username = user.username
            row.display_name = user.display_name
            row.updated_at = datetime.now(UTC)
        return row

    @staticmethod
    async def _get_or_create_player(
        db: AsyncSession,
        user_id: int,
        season: str,
    ) -> PvPPlayerRow:
        key = {"user_id": user_id, "season": season}
        row = await db.get(PvPPlayerRow, key, with_for_update=True)
        if row is None:
            row = PvPPlayerRow(user_id=user_id, season=season, rating=1000)
            db.add(row)
            await db.flush()
        return row

    @staticmethod
    def _apply_game_result(row: PvPPlayerRow, score: float) -> None:
        row.games += 1
        if score == 1.0:
            row.wins += 1
        elif score == 0.5:
            row.draws += 1
        else:
            row.losses += 1

    @staticmethod
    def _rating_view(player: PvPPlayerRow, profile: UserProfileRow) -> PvPRatingView:
        return PvPRatingView(
            user_id=player.user_id,
            display_name=profile.display_name,
            username=profile.username,
            season=player.season,
            rating=player.rating,
            games=player.games,
            wins=player.wins,
            draws=player.draws,
            losses=player.losses,
        )

    @staticmethod
    def _match_to_model(row: PvPMatchRow) -> PvPMatchHistoryEntry:
        outcome = row.outcome
        if outcome not in {"judged", "draw", "forfeit"}:
            raise ValueError("Unknown stored PvP outcome")
        return PvPMatchHistoryEntry(
            match_id=row.match_id,
            season=row.season,
            topic=row.topic,
            pro_user_id=row.pro_user_id,
            con_user_id=row.con_user_id,
            winner_user_id=row.winner_user_id,
            outcome=outcome,
            pro_rating_before=row.pro_rating_before,
            pro_rating_after=row.pro_rating_after,
            con_rating_before=row.con_rating_before,
            con_rating_after=row.con_rating_after,
            reason=row.reason,
            started_at=row.started_at,
            ended_at=row.ended_at,
        )
