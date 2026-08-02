from __future__ import annotations

from statistics import fmean

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .coaching_models import (
    CoachingResult,
    CoachingSummary,
    MatchReview,
    SkillScores,
)
from .database import PvPMatchRow, UserProfileRow


class CoachingRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        window_matches: int = 10,
    ) -> None:
        if not 1 <= window_matches <= 50:
            raise ValueError("window_matches must be between 1 and 50")
        self.sessions = sessions
        self.window_matches = window_matches

    async def match_review(
        self,
        user_id: int,
        season: str,
        match_id: str | None = None,
    ) -> MatchReview | None:
        query = (
            select(PvPMatchRow)
            .where(
                PvPMatchRow.season == season,
                or_(
                    PvPMatchRow.pro_user_id == user_id,
                    PvPMatchRow.con_user_id == user_id,
                ),
            )
            .order_by(PvPMatchRow.ended_at.desc(), PvPMatchRow.match_id.desc())
        )
        if match_id is not None:
            query = query.where(PvPMatchRow.match_id == match_id).limit(1)
        else:
            query = query.limit(max(50, self.window_matches * 5))

        async with self.sessions() as db:
            rows = list(await db.scalars(query))
            for row in rows:
                opponent_id = self._opponent_id(row, user_id)
                review = self._review_from_row(row, user_id, opponent_name="Соперник")
                if review is None:
                    continue
                profile = await db.get(UserProfileRow, opponent_id)
                if profile is None:
                    return review
                return self._review_from_row(
                    row,
                    user_id,
                    opponent_name=profile.display_name,
                )
        return None

    async def summary(self, user_id: int, season: str) -> CoachingSummary | None:
        scan_limit = max(50, self.window_matches * 5)
        async with self.sessions() as db:
            rows = list(
                await db.scalars(
                    select(PvPMatchRow)
                    .where(
                        PvPMatchRow.season == season,
                        or_(
                            PvPMatchRow.pro_user_id == user_id,
                            PvPMatchRow.con_user_id == user_id,
                        ),
                    )
                    .order_by(
                        PvPMatchRow.ended_at.desc(),
                        PvPMatchRow.match_id.desc(),
                    )
                    .limit(scan_limit)
                )
            )

        reviews: list[MatchReview] = []
        for row in rows:
            review = self._review_from_row(row, user_id, opponent_name="Соперник")
            if review is not None:
                reviews.append(review)
            if len(reviews) >= self.window_matches:
                break
        if not reviews:
            return None

        averages = SkillScores(
            logic=fmean(item.own_scores.logic for item in reviews),
            evidence=fmean(item.own_scores.evidence for item in reviews),
            rebuttal=fmean(item.own_scores.rebuttal for item in reviews),
        )
        wins = sum(item.result is CoachingResult.WIN for item in reviews)
        draws = sum(item.result is CoachingResult.DRAW for item in reviews)
        losses = sum(item.result is CoachingResult.LOSS for item in reviews)

        trend_delta: float | None = None
        half = len(reviews) // 2
        if half >= 2:
            recent_average = fmean(item.own_scores.total for item in reviews[:half])
            older_average = fmean(item.own_scores.total for item in reviews[-half:])
            trend_delta = recent_average - older_average

        pro_totals = [item.own_scores.total for item in reviews if item.stance == "за"]
        con_totals = [item.own_scores.total for item in reviews if item.stance == "против"]
        return CoachingSummary(
            season=season,
            analyzed_matches=len(reviews),
            requested_window=self.window_matches,
            averages=averages,
            wins=wins,
            draws=draws,
            losses=losses,
            trend_delta=trend_delta,
            pro_average_total=fmean(pro_totals) if pro_totals else None,
            con_average_total=fmean(con_totals) if con_totals else None,
        )

    @classmethod
    def _review_from_row(
        cls,
        row: PvPMatchRow,
        user_id: int,
        *,
        opponent_name: str,
    ) -> MatchReview | None:
        if row.pro_user_id == user_id:
            own_scores = cls._parse_scores(row.pro_scores)
            opponent_scores = cls._parse_scores(row.con_scores)
            opponent_id = row.con_user_id
            stance = "за"
            rating_delta = row.pro_rating_after - row.pro_rating_before
        elif row.con_user_id == user_id:
            own_scores = cls._parse_scores(row.con_scores)
            opponent_scores = cls._parse_scores(row.pro_scores)
            opponent_id = row.pro_user_id
            stance = "против"
            rating_delta = row.con_rating_after - row.con_rating_before
        else:
            return None
        if own_scores is None or opponent_scores is None:
            return None

        if row.winner_user_id is None:
            result = CoachingResult.DRAW
        elif row.winner_user_id == user_id:
            result = CoachingResult.WIN
        else:
            result = CoachingResult.LOSS
        return MatchReview(
            match_id=row.match_id,
            season=row.season,
            topic=row.topic,
            opponent_user_id=opponent_id,
            opponent_name=opponent_name,
            stance=stance,
            result=result,
            rated=row.rated,
            rating_delta=rating_delta,
            own_scores=own_scores,
            opponent_scores=opponent_scores,
            verdict_reason=row.reason,
            ended_at=row.ended_at,
        )

    @staticmethod
    def _parse_scores(raw: object) -> SkillScores | None:
        if not isinstance(raw, dict):
            return None
        values: list[float] = []
        for key in ("logic", "evidence", "rebuttal"):
            value = raw.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            normalized = float(value)
            if not 0 <= normalized <= 10:
                return None
            values.append(normalized)
        return SkillScores(
            logic=values[0],
            evidence=values[1],
            rebuttal=values[2],
        )

    @staticmethod
    def _opponent_id(row: PvPMatchRow, user_id: int) -> int:
        if row.pro_user_id == user_id:
            return row.con_user_id
        if row.con_user_id == user_id:
            return row.pro_user_id
        raise ValueError("User is not a participant of this match")
