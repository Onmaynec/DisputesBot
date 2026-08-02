from __future__ import annotations

from collections import Counter
from statistics import fmean

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPMatchRow, PvPPlayerRow, UserProfileRow
from .league_models import DEFAULT_PLACEMENT_GAMES, league_status
from .ranked_reward_database import PvPRankedRewardClaimRow
from .season_insight_models import (
    CareerRecords,
    SeasonComparison,
    SeasonRecap,
    SeasonSkillAverages,
)


class SeasonInsightRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        placement_games: int = DEFAULT_PLACEMENT_GAMES,
        max_seasons: int = 20,
    ) -> None:
        if placement_games < 0:
            raise ValueError("placement_games must not be negative")
        if not 1 <= max_seasons <= 50:
            raise ValueError("max_seasons must be between 1 and 50")
        self.sessions = sessions
        self.placement_games = placement_games
        self.max_seasons = max_seasons

    async def recap(self, user_id: int, season: str) -> SeasonRecap | None:
        normalized = self._normalize_season(season)
        if normalized is None:
            return None

        async with self.sessions() as db:
            player = await db.get(
                PvPPlayerRow,
                {"user_id": user_id, "season": normalized},
            )
            if player is None:
                return None

            ranked_ids = list(
                await db.scalars(
                    self._ranking_query(normalized).with_only_columns(PvPPlayerRow.user_id)
                )
            )
            matches = list(
                await db.scalars(
                    select(PvPMatchRow)
                    .where(
                        PvPMatchRow.season == normalized,
                        or_(
                            PvPMatchRow.pro_user_id == user_id,
                            PvPMatchRow.con_user_id == user_id,
                        ),
                    )
                    .order_by(PvPMatchRow.ended_at.asc(), PvPMatchRow.match_id.asc())
                )
            )
            claim_count, claim_tokens = (
                await db.execute(
                    select(
                        func.count(PvPRankedRewardClaimRow.league_id),
                        func.coalesce(func.sum(PvPRankedRewardClaimRow.reward_tokens), 0),
                    ).where(
                        PvPRankedRewardClaimRow.user_id == user_id,
                        PvPRankedRewardClaimRow.season == normalized,
                    )
                )
            ).one()

            favorite_id, favorite_matches = self._favorite_opponent(matches, user_id)
            favorite_name: str | None = None
            if favorite_id is not None:
                profile = await db.get(UserProfileRow, favorite_id)
                favorite_name = profile.display_name if profile is not None else "Соперник"

        starting_rating, peak_rating = self._rating_path(
            matches,
            user_id,
            fallback=player.rating,
        )
        rated_matches = sum(bool(match.rated) for match in matches)
        unique_opponents = len({self._opponent_id(match, user_id) for match in matches})
        skill_rows = [
            parsed
            for match in matches
            if (parsed := self._scores_for(match, user_id)) is not None
        ]
        skills = None
        if skill_rows:
            skills = SeasonSkillAverages(
                logic=fmean(item[0] for item in skill_rows),
                evidence=fmean(item[1] for item in skill_rows),
                rebuttal=fmean(item[2] for item in skill_rows),
                scored_matches=len(skill_rows),
            )

        return SeasonRecap(
            user_id=user_id,
            season=normalized,
            rating=player.rating,
            starting_rating=starting_rating,
            peak_rating=peak_rating,
            rank=ranked_ids.index(user_id) + 1,
            total_players=len(ranked_ids),
            games=player.games,
            wins=player.wins,
            draws=player.draws,
            losses=player.losses,
            rated_matches=rated_matches,
            unrated_matches=len(matches) - rated_matches,
            unique_opponents=unique_opponents,
            longest_win_streak=self._longest_win_streak(matches, user_id),
            favorite_opponent_id=favorite_id,
            favorite_opponent_name=favorite_name,
            favorite_opponent_matches=favorite_matches,
            claimed_milestones=int(claim_count),
            claimed_tokens=int(claim_tokens),
            skills=skills,
            status=league_status(
                player.rating,
                player.games,
                placement_games=self.placement_games,
            ),
            last_activity=player.updated_at,
        )

    async def compare(
        self,
        user_id: int,
        older_season: str,
        newer_season: str,
    ) -> SeasonComparison | None:
        older_id = self._normalize_season(older_season)
        newer_id = self._normalize_season(newer_season)
        if older_id is None or newer_id is None or older_id == newer_id:
            return None
        older = await self.recap(user_id, older_id)
        newer = await self.recap(user_id, newer_id)
        if older is None or newer is None:
            return None
        return SeasonComparison(older=older, newer=newer)

    async def compare_recent(self, user_id: int) -> SeasonComparison | None:
        seasons = await self._season_ids(user_id, limit=2)
        if len(seasons) < 2:
            return None
        return await self.compare(user_id, seasons[1], seasons[0])

    async def records(self, user_id: int) -> CareerRecords | None:
        season_ids = await self._season_ids(user_id, limit=self.max_seasons)
        recaps = [
            recap
            for season in season_ids
            if (recap := await self.recap(user_id, season)) is not None
        ]
        if not recaps:
            return None

        eligible_win_rate = [item for item in recaps if item.games >= 5]
        if not eligible_win_rate:
            eligible_win_rate = [item for item in recaps if item.games > 0] or recaps

        return CareerRecords(
            user_id=user_id,
            seasons=tuple(recaps),
            highest_final=max(
                recaps,
                key=lambda item: (item.rating, item.peak_rating, item.games, item.season),
            ),
            highest_peak=max(
                recaps,
                key=lambda item: (item.peak_rating, item.rating, item.games, item.season),
            ),
            most_wins=max(
                recaps,
                key=lambda item: (item.wins, item.win_rate, item.rating, item.season),
            ),
            most_games=max(
                recaps,
                key=lambda item: (item.games, item.wins, item.rating, item.season),
            ),
            best_win_rate=max(
                eligible_win_rate,
                key=lambda item: (item.win_rate, item.wins, item.rating, item.season),
            ),
            biggest_gain=max(
                recaps,
                key=lambda item: (item.net_rating, item.peak_rating, item.games, item.season),
            ),
            longest_streak=max(
                recaps,
                key=lambda item: (
                    item.longest_win_streak,
                    item.wins,
                    item.rating,
                    item.season,
                ),
            ),
        )

    async def _season_ids(self, user_id: int, *, limit: int) -> list[str]:
        safe_limit = max(1, min(limit, self.max_seasons))
        async with self.sessions() as db:
            return list(
                await db.scalars(
                    select(PvPPlayerRow.season)
                    .where(PvPPlayerRow.user_id == user_id)
                    .order_by(PvPPlayerRow.updated_at.desc(), PvPPlayerRow.season.desc())
                    .limit(safe_limit)
                )
            )

    @staticmethod
    def _normalize_season(season: str) -> str | None:
        normalized = season.strip()
        if not normalized or len(normalized) > 32 or any(char.isspace() for char in normalized):
            return None
        return normalized

    @staticmethod
    def _ranking_query(season: str):
        return (
            select(PvPPlayerRow)
            .where(PvPPlayerRow.season == season)
            .order_by(
                PvPPlayerRow.rating.desc(),
                PvPPlayerRow.games.desc(),
                PvPPlayerRow.updated_at.asc(),
                PvPPlayerRow.user_id.asc(),
            )
        )

    @classmethod
    def _rating_path(
        cls,
        matches: list[PvPMatchRow],
        user_id: int,
        *,
        fallback: int,
    ) -> tuple[int, int]:
        if not matches:
            return fallback, fallback
        first_before, _ = cls._ratings_for(matches[0], user_id)
        values = [fallback, first_before]
        for match in matches:
            before, after = cls._ratings_for(match, user_id)
            values.extend((before, after))
        return first_before, max(values)

    @classmethod
    def _longest_win_streak(cls, matches: list[PvPMatchRow], user_id: int) -> int:
        longest = 0
        current = 0
        for match in matches:
            if match.winner_user_id == user_id:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    @classmethod
    def _favorite_opponent(
        cls,
        matches: list[PvPMatchRow],
        user_id: int,
    ) -> tuple[int | None, int]:
        counts: Counter[int] = Counter(cls._opponent_id(match, user_id) for match in matches)
        if not counts:
            return None, 0
        opponent_id, count = min(counts.items(), key=lambda item: (-item[1], item[0]))
        return opponent_id, count

    @classmethod
    def _scores_for(
        cls,
        match: PvPMatchRow,
        user_id: int,
    ) -> tuple[float, float, float] | None:
        if match.pro_user_id == user_id:
            raw = match.pro_scores
        elif match.con_user_id == user_id:
            raw = match.con_scores
        else:
            return None
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
        return values[0], values[1], values[2]

    @staticmethod
    def _ratings_for(match: PvPMatchRow, user_id: int) -> tuple[int, int]:
        if match.pro_user_id == user_id:
            return match.pro_rating_before, match.pro_rating_after
        if match.con_user_id == user_id:
            return match.con_rating_before, match.con_rating_after
        raise ValueError("user is not a participant of the match")

    @staticmethod
    def _opponent_id(match: PvPMatchRow, user_id: int) -> int:
        if match.pro_user_id == user_id:
            return match.con_user_id
        if match.con_user_id == user_id:
            return match.pro_user_id
        raise ValueError("user is not a participant of the match")
