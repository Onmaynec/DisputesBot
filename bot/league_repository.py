from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPMatchRow, PvPPlayerRow, UserProfileRow
from .league_models import (
    DEFAULT_PLACEMENT_GAMES,
    LEAGUE_CATALOG,
    LeagueDistribution,
    LeagueDistributionEntry,
    LeaguePlayerView,
    LeagueStanding,
    league_status,
)


class LeagueRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        placement_games: int = DEFAULT_PLACEMENT_GAMES,
        recent_matches: int = 5,
    ) -> None:
        if placement_games < 0:
            raise ValueError("placement_games must not be negative")
        if not 1 <= recent_matches <= 20:
            raise ValueError("recent_matches must be between 1 and 20")
        self.sessions = sessions
        self.placement_games = placement_games
        self.recent_matches = recent_matches

    async def player(self, user_id: int, season: str) -> LeaguePlayerView | None:
        async with self.sessions() as db:
            row = (
                await db.execute(
                    select(PvPPlayerRow, UserProfileRow)
                    .join(UserProfileRow, UserProfileRow.user_id == PvPPlayerRow.user_id)
                    .where(
                        PvPPlayerRow.user_id == user_id,
                        PvPPlayerRow.season == season,
                    )
                )
            ).one_or_none()
            if row is None:
                return None
            player, profile = row
            ranked_ids = list(
                await db.scalars(
                    self._ranking_query(season).with_only_columns(PvPPlayerRow.user_id)
                )
            )
            recent = list(
                await db.scalars(
                    select(PvPMatchRow)
                    .where(
                        PvPMatchRow.season == season,
                        or_(
                            PvPMatchRow.pro_user_id == user_id,
                            PvPMatchRow.con_user_id == user_id,
                        ),
                    )
                    .order_by(PvPMatchRow.ended_at.desc(), PvPMatchRow.match_id.desc())
                    .limit(self.recent_matches)
                )
            )

        recent_delta = sum(self._rating_delta(match, user_id) for match in recent)
        recent_form = tuple(
            reversed(tuple(self._outcome_marker(match, user_id) for match in recent))
        )
        return LeaguePlayerView(
            user_id=player.user_id,
            display_name=profile.display_name,
            username=profile.username,
            season=player.season,
            rating=player.rating,
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
            recent_rating_delta=recent_delta,
            recent_form=recent_form,
        )

    async def top(self, season: str, *, limit: int = 10) -> list[LeagueStanding]:
        safe_limit = max(1, min(limit, 50))
        async with self.sessions() as db:
            rows = (
                await db.execute(self._ranking_query(season).limit(safe_limit))
            ).all()
        return [
            LeagueStanding(
                user_id=player.user_id,
                display_name=profile.display_name,
                username=profile.username,
                rating=player.rating,
                games=player.games,
                status=league_status(
                    player.rating,
                    player.games,
                    placement_games=self.placement_games,
                ),
            )
            for player, profile in rows
        ]

    async def distribution(self, season: str) -> LeagueDistribution:
        async with self.sessions() as db:
            players = list(
                await db.scalars(
                    select(PvPPlayerRow).where(PvPPlayerRow.season == season)
                )
            )

        counts = {definition.league_id.value: 0 for definition in LEAGUE_CATALOG}
        placement_count = 0
        for player in players:
            status = league_status(
                player.rating,
                player.games,
                placement_games=self.placement_games,
            )
            if status.is_placement:
                placement_count += 1
            else:
                assert status.league is not None
                counts[status.league.league_id.value] += 1

        entries = [
            LeagueDistributionEntry(
                key="placement",
                name="Калибровка",
                icon="🧭",
                players=placement_count,
            )
        ]
        entries.extend(
            LeagueDistributionEntry(
                key=definition.league_id.value,
                name=definition.name,
                icon=definition.icon,
                players=counts[definition.league_id.value],
            )
            for definition in reversed(LEAGUE_CATALOG)
        )
        return LeagueDistribution(
            season=season,
            total_players=len(players),
            entries=tuple(entries),
        )

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

    @staticmethod
    def _rating_delta(match: PvPMatchRow, user_id: int) -> int:
        if not match.rated:
            return 0
        if match.pro_user_id == user_id:
            return match.pro_rating_after - match.pro_rating_before
        return match.con_rating_after - match.con_rating_before

    @staticmethod
    def _outcome_marker(match: PvPMatchRow, user_id: int) -> str:
        if match.winner_user_id is None:
            return "Н"
        return "В" if match.winner_user_id == user_id else "П"
