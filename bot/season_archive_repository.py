from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPMatchRow, PvPPlayerRow, UserProfileRow
from .league_models import DEFAULT_PLACEMENT_GAMES, league_status
from .season_archive_models import (
    CareerSeason,
    CareerSummary,
    SeasonArchive,
    SeasonArchiveStanding,
    SeasonCatalogEntry,
)


class SeasonArchiveRepository:
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

    async def career(self, user_id: int) -> CareerSummary | None:
        async with self.sessions() as db:
            profile = await db.get(UserProfileRow, user_id)
            players = list(
                await db.scalars(
                    select(PvPPlayerRow)
                    .where(PvPPlayerRow.user_id == user_id)
                    .order_by(PvPPlayerRow.updated_at.desc(), PvPPlayerRow.season.desc())
                    .limit(self.max_seasons)
                )
            )
            if profile is None or not players:
                return None

            seasons: list[CareerSeason] = []
            for player in players:
                ranked_ids = list(
                    await db.scalars(
                        self._ranking_query(player.season).with_only_columns(
                            PvPPlayerRow.user_id
                        )
                    )
                )
                matches = list(
                    await db.scalars(
                        select(PvPMatchRow)
                        .where(
                            PvPMatchRow.season == player.season,
                            or_(
                                PvPMatchRow.pro_user_id == user_id,
                                PvPMatchRow.con_user_id == user_id,
                            ),
                        )
                        .order_by(PvPMatchRow.ended_at.asc(), PvPMatchRow.match_id.asc())
                    )
                )
                starting_rating, peak_rating = self._rating_path(
                    matches,
                    user_id,
                    fallback=player.rating,
                )
                seasons.append(
                    CareerSeason(
                        season=player.season,
                        rating=player.rating,
                        starting_rating=starting_rating,
                        peak_rating=peak_rating,
                        rank=ranked_ids.index(user_id) + 1,
                        games=player.games,
                        wins=player.wins,
                        draws=player.draws,
                        losses=player.losses,
                        status=league_status(
                            player.rating,
                            player.games,
                            placement_games=self.placement_games,
                        ),
                        last_activity=player.updated_at,
                    )
                )

        return CareerSummary(
            user_id=user_id,
            display_name=profile.display_name,
            username=profile.username,
            seasons=tuple(seasons),
            total_games=sum(item.games for item in seasons),
            total_wins=sum(item.wins for item in seasons),
            total_draws=sum(item.draws for item in seasons),
            total_losses=sum(item.losses for item in seasons),
            peak_rating=max(item.peak_rating for item in seasons),
        )

    async def archive(self, season: str, *, limit: int = 10) -> SeasonArchive | None:
        normalized = season.strip()
        if not normalized or len(normalized) > 32:
            return None
        safe_limit = max(1, min(limit, 50))
        async with self.sessions() as db:
            total_players = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PvPPlayerRow)
                    .where(PvPPlayerRow.season == normalized)
                )
                or 0
            )
            if total_players == 0:
                return None
            total_matches = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PvPMatchRow)
                    .where(PvPMatchRow.season == normalized)
                )
                or 0
            )
            rows = (
                await db.execute(self._ranking_query(normalized).limit(safe_limit))
            ).all()

        standings = tuple(
            SeasonArchiveStanding(
                rank=rank,
                user_id=player.user_id,
                display_name=profile.display_name,
                username=profile.username,
                rating=player.rating,
                games=player.games,
                wins=player.wins,
                draws=player.draws,
                losses=player.losses,
                status=league_status(
                    player.rating,
                    player.games,
                    placement_games=self.placement_games,
                ),
            )
            for rank, (player, profile) in enumerate(rows, start=1)
        )
        return SeasonArchive(
            season=normalized,
            total_players=total_players,
            total_matches=total_matches,
            standings=standings,
        )

    async def catalog(self, *, limit: int | None = None) -> list[SeasonCatalogEntry]:
        safe_limit = self.max_seasons if limit is None else max(1, min(limit, 50))
        activity = func.max(PvPPlayerRow.updated_at).label("last_activity")
        async with self.sessions() as db:
            season_rows = (
                await db.execute(
                    select(
                        PvPPlayerRow.season,
                        func.count(PvPPlayerRow.user_id).label("players"),
                        activity,
                    )
                    .group_by(PvPPlayerRow.season)
                    .order_by(activity.desc(), PvPPlayerRow.season.desc())
                    .limit(safe_limit)
                )
            ).all()
            entries: list[SeasonCatalogEntry] = []
            for season, players, last_activity in season_rows:
                champion_row = (
                    await db.execute(self._ranking_query(season).limit(1))
                ).one_or_none()
                if champion_row is None:
                    continue
                champion, profile = champion_row
                matches = int(
                    await db.scalar(
                        select(func.count())
                        .select_from(PvPMatchRow)
                        .where(PvPMatchRow.season == season)
                    )
                    or 0
                )
                entries.append(
                    SeasonCatalogEntry(
                        season=season,
                        players=int(players),
                        matches=matches,
                        champion_user_id=champion.user_id,
                        champion_name=profile.display_name,
                        champion_username=profile.username,
                        champion_rating=champion.rating,
                        champion_games=champion.games,
                        champion_status=league_status(
                            champion.rating,
                            champion.games,
                            placement_games=self.placement_games,
                        ),
                        last_activity=last_activity,
                    )
                )
        return entries

    @staticmethod
    def _ranking_query(season: str):
        return (
            select(PvPPlayerRow, UserProfileRow)
            .join(UserProfileRow, UserProfileRow.user_id == PvPPlayerRow.user_id)
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

    @staticmethod
    def _ratings_for(match: PvPMatchRow, user_id: int) -> tuple[int, int]:
        if match.pro_user_id == user_id:
            return match.pro_rating_before, match.pro_rating_after
        if match.con_user_id == user_id:
            return match.con_rating_before, match.con_rating_after
        raise ValueError("user is not a participant of the match")
