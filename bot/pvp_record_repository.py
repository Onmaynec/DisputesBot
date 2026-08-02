from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .database import PvPMatchRow, PvPPlayerRow, UserProfileRow
from .pvp_record_models import (
    PersonalMatchRecord,
    PersonalRivalRecord,
    PersonalStreakRecord,
    PvPRecordBook,
    SeasonPlayerRecord,
    SeasonRecordBook,
    SeasonRivalryRecord,
    SeasonUpsetRecord,
)


class PvPRecordRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def personal(self, user_id: int) -> PvPRecordBook | None:
        async with self.sessions() as db:
            profile = await db.get(UserProfileRow, user_id)
            matches = list(
                await db.scalars(
                    select(PvPMatchRow)
                    .where(
                        or_(
                            PvPMatchRow.pro_user_id == user_id,
                            PvPMatchRow.con_user_id == user_id,
                        )
                    )
                    .order_by(
                        PvPMatchRow.season.asc(),
                        PvPMatchRow.ended_at.asc(),
                        PvPMatchRow.match_id.asc(),
                    )
                )
            )
            if profile is None or not matches:
                return None

            opponent_ids = {self._opponent_id(match, user_id) for match in matches}
            opponent_profiles = list(
                await db.scalars(
                    select(UserProfileRow).where(UserProfileRow.user_id.in_(opponent_ids))
                )
            )

        names = {item.user_id: item.display_name for item in opponent_profiles}
        wins = 0
        draws = 0
        losses = 0
        current_streak = 0
        current_season: str | None = None
        longest_streak: PersonalStreakRecord | None = None
        best_gain: PersonalMatchRecord | None = None
        biggest_upset: PersonalMatchRecord | None = None
        highest_score: PersonalMatchRecord | None = None
        rival_counts: dict[int, int] = defaultdict(int)
        rival_last_match: dict[int, datetime] = {}

        for match in matches:
            if current_season != match.season:
                current_season = match.season
                current_streak = 0

            opponent_id = self._opponent_id(match, user_id)
            opponent_name = names.get(opponent_id, "Удалённый игрок")
            rival_counts[opponent_id] += 1
            previous_last = rival_last_match.get(opponent_id)
            if previous_last is None or self._time_key(match.ended_at) > self._time_key(
                previous_last
            ):
                rival_last_match[opponent_id] = match.ended_at

            if match.winner_user_id == user_id:
                wins += 1
                current_streak += 1
                if longest_streak is None or current_streak > longest_streak.wins:
                    longest_streak = PersonalStreakRecord(
                        wins=current_streak,
                        season=match.season,
                    )
            elif match.winner_user_id is None:
                draws += 1
                current_streak = 0
            else:
                losses += 1
                current_streak = 0

            own_before, own_after, opponent_before = self._ratings(match, user_id)
            gain = own_after - own_before
            if match.rated and gain > 0:
                candidate = PersonalMatchRecord(
                    season=match.season,
                    match_id=match.match_id,
                    opponent_user_id=opponent_id,
                    opponent_name=opponent_name,
                    value=float(gain),
                    ended_at=match.ended_at,
                )
                if self._prefer_personal(candidate, best_gain):
                    best_gain = candidate

            upset_gap = opponent_before - own_before
            if match.rated and match.winner_user_id == user_id and upset_gap > 0:
                candidate = PersonalMatchRecord(
                    season=match.season,
                    match_id=match.match_id,
                    opponent_user_id=opponent_id,
                    opponent_name=opponent_name,
                    value=float(upset_gap),
                    ended_at=match.ended_at,
                )
                if self._prefer_personal(candidate, biggest_upset):
                    biggest_upset = candidate

            score = self._score_total(
                match.pro_scores if match.pro_user_id == user_id else match.con_scores
            )
            if score is not None:
                candidate = PersonalMatchRecord(
                    season=match.season,
                    match_id=match.match_id,
                    opponent_user_id=opponent_id,
                    opponent_name=opponent_name,
                    value=score,
                    ended_at=match.ended_at,
                )
                if self._prefer_personal(candidate, highest_score):
                    highest_score = candidate

        favorite_rival: PersonalRivalRecord | None = None
        if rival_counts:
            opponent_id = min(
                rival_counts,
                key=lambda item: (
                    -rival_counts[item],
                    -self._time_key(rival_last_match[item]),
                    item,
                ),
            )
            favorite_rival = PersonalRivalRecord(
                opponent_user_id=opponent_id,
                opponent_name=names.get(opponent_id, "Удалённый игрок"),
                matches=rival_counts[opponent_id],
                last_match_at=rival_last_match[opponent_id],
            )

        return PvPRecordBook(
            user_id=user_id,
            display_name=profile.display_name,
            seasons=len({match.season for match in matches}),
            total_matches=len(matches),
            wins=wins,
            draws=draws,
            losses=losses,
            distinct_opponents=len(opponent_ids),
            longest_win_streak=longest_streak,
            best_rating_gain=best_gain,
            biggest_upset=biggest_upset,
            highest_score=highest_score,
            favorite_rival=favorite_rival,
        )

    async def season(self, season: str) -> SeasonRecordBook | None:
        normalized = season.strip()
        if not normalized or len(normalized) > 32:
            return None

        async with self.sessions() as db:
            player_rows = (
                await db.execute(
                    select(PvPPlayerRow, UserProfileRow)
                    .join(UserProfileRow, UserProfileRow.user_id == PvPPlayerRow.user_id)
                    .where(PvPPlayerRow.season == normalized)
                )
            ).all()
            matches = list(
                await db.scalars(
                    select(PvPMatchRow)
                    .where(PvPMatchRow.season == normalized)
                    .order_by(PvPMatchRow.ended_at.asc(), PvPMatchRow.match_id.asc())
                )
            )
            if not player_rows and not matches:
                return None

            participant_ids = {
                user_id
                for match in matches
                for user_id in (match.pro_user_id, match.con_user_id)
            }
            if participant_ids:
                profiles = list(
                    await db.scalars(
                        select(UserProfileRow).where(
                            UserProfileRow.user_id.in_(participant_ids)
                        )
                    )
                )
            else:
                profiles = []

        names = {profile.user_id: profile.display_name for profile in profiles}
        players = {player.user_id: player for player, _ in player_rows}
        for player, profile in player_rows:
            names[player.user_id] = profile.display_name

        return SeasonRecordBook(
            season=normalized,
            total_players=len(player_rows),
            total_matches=len(matches),
            most_wins=self._player_record(player_rows, metric="wins"),
            most_games=self._player_record(player_rows, metric="games"),
            longest_win_streak=self._season_longest_streak(matches, players, names),
            biggest_upset=self._season_biggest_upset(matches, names),
            busiest_rivalry=self._season_busiest_rivalry(matches, names),
        )

    @classmethod
    def _season_longest_streak(
        cls,
        matches: list[PvPMatchRow],
        players: dict[int, PvPPlayerRow],
        names: dict[int, str],
    ) -> SeasonPlayerRecord | None:
        current: dict[int, int] = defaultdict(int)
        best_user_id: int | None = None
        best_wins = 0
        best_at: datetime | None = None

        for match in matches:
            for user_id in (match.pro_user_id, match.con_user_id):
                if match.winner_user_id == user_id:
                    current[user_id] += 1
                    if (
                        current[user_id] > best_wins
                        or (
                            current[user_id] == best_wins
                            and best_at is not None
                            and (cls._time_key(match.ended_at), user_id)
                            < (cls._time_key(best_at), best_user_id or user_id)
                        )
                    ):
                        best_user_id = user_id
                        best_wins = current[user_id]
                        best_at = match.ended_at
                else:
                    current[user_id] = 0

        if best_user_id is None:
            return None
        player = players.get(best_user_id)
        return SeasonPlayerRecord(
            user_id=best_user_id,
            display_name=names.get(best_user_id, "Удалённый игрок"),
            value=best_wins,
            rating=player.rating if player is not None else 0,
            games=player.games if player is not None else 0,
        )

    @classmethod
    def _season_biggest_upset(
        cls,
        matches: list[PvPMatchRow],
        names: dict[int, str],
    ) -> SeasonUpsetRecord | None:
        best: SeasonUpsetRecord | None = None
        for match in matches:
            if not match.rated or match.winner_user_id is None:
                continue
            if match.winner_user_id == match.pro_user_id:
                winner_id = match.pro_user_id
                loser_id = match.con_user_id
                winner_before = match.pro_rating_before
                loser_before = match.con_rating_before
            elif match.winner_user_id == match.con_user_id:
                winner_id = match.con_user_id
                loser_id = match.pro_user_id
                winner_before = match.con_rating_before
                loser_before = match.pro_rating_before
            else:
                continue
            gap = loser_before - winner_before
            if gap <= 0:
                continue
            candidate = SeasonUpsetRecord(
                winner_user_id=winner_id,
                winner_name=names.get(winner_id, "Удалённый игрок"),
                loser_user_id=loser_id,
                loser_name=names.get(loser_id, "Удалённый игрок"),
                elo_gap=gap,
                ended_at=match.ended_at,
                match_id=match.match_id,
            )
            if (
                best is None
                or candidate.elo_gap > best.elo_gap
                or (
                    candidate.elo_gap == best.elo_gap
                    and (cls._time_key(candidate.ended_at), candidate.match_id)
                    < (cls._time_key(best.ended_at), best.match_id)
                )
            ):
                best = candidate
        return best

    @classmethod
    def _season_busiest_rivalry(
        cls,
        matches: list[PvPMatchRow],
        names: dict[int, str],
    ) -> SeasonRivalryRecord | None:
        counts: dict[tuple[int, int], int] = defaultdict(int)
        last_match: dict[tuple[int, int], datetime] = {}
        for match in matches:
            pair = tuple(sorted((match.pro_user_id, match.con_user_id)))
            counts[pair] += 1
            previous = last_match.get(pair)
            if previous is None or cls._time_key(match.ended_at) > cls._time_key(previous):
                last_match[pair] = match.ended_at
        if not counts:
            return None
        pair = min(
            counts,
            key=lambda item: (
                -counts[item],
                -cls._time_key(last_match[item]),
                item[0],
                item[1],
            ),
        )
        first_id, second_id = pair
        return SeasonRivalryRecord(
            first_user_id=first_id,
            first_name=names.get(first_id, "Удалённый игрок"),
            second_user_id=second_id,
            second_name=names.get(second_id, "Удалённый игрок"),
            matches=counts[pair],
            last_match_at=last_match[pair],
        )

    @classmethod
    def _player_record(
        cls,
        rows: list[tuple[PvPPlayerRow, UserProfileRow]],
        *,
        metric: str,
    ) -> SeasonPlayerRecord | None:
        if not rows:
            return None
        if metric == "wins":
            player, profile = min(
                rows,
                key=lambda item: (
                    -item[0].wins,
                    -item[0].rating,
                    -item[0].games,
                    cls._time_key(item[0].updated_at),
                    item[0].user_id,
                ),
            )
            value = player.wins
        elif metric == "games":
            player, profile = min(
                rows,
                key=lambda item: (
                    -item[0].games,
                    -item[0].rating,
                    -item[0].wins,
                    cls._time_key(item[0].updated_at),
                    item[0].user_id,
                ),
            )
            value = player.games
        else:
            raise ValueError("unsupported player record metric")
        return SeasonPlayerRecord(
            user_id=player.user_id,
            display_name=profile.display_name,
            value=value,
            rating=player.rating,
            games=player.games,
        )

    @classmethod
    def _prefer_personal(
        cls,
        candidate: PersonalMatchRecord,
        current: PersonalMatchRecord | None,
    ) -> bool:
        if current is None or candidate.value > current.value:
            return True
        if candidate.value < current.value:
            return False
        return (cls._time_key(candidate.ended_at), candidate.match_id) < (
            cls._time_key(current.ended_at),
            current.match_id,
        )

    @staticmethod
    def _score_total(raw: object) -> float | None:
        if not isinstance(raw, dict):
            return None
        total = 0.0
        for key in ("logic", "evidence", "rebuttal"):
            value = raw.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            normalized = float(value)
            if not 0 <= normalized <= 10:
                return None
            total += normalized
        return total

    @staticmethod
    def _opponent_id(match: PvPMatchRow, user_id: int) -> int:
        if match.pro_user_id == user_id:
            return match.con_user_id
        if match.con_user_id == user_id:
            return match.pro_user_id
        raise ValueError("user is not a participant of the match")

    @staticmethod
    def _ratings(match: PvPMatchRow, user_id: int) -> tuple[int, int, int]:
        if match.pro_user_id == user_id:
            return (
                match.pro_rating_before,
                match.pro_rating_after,
                match.con_rating_before,
            )
        if match.con_user_id == user_id:
            return (
                match.con_rating_before,
                match.con_rating_after,
                match.pro_rating_before,
            )
        raise ValueError("user is not a participant of the match")

    @staticmethod
    def _time_key(value: datetime) -> float:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.timestamp()
