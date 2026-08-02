import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.database import Database, PvPMatchRow, PvPPlayerRow, UserProfileRow
from bot.pvp_record_repository import PvPRecordRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


def profile(user_id: int) -> UserProfileRow:
    return UserProfileRow(
        user_id=user_id,
        username=f"user{user_id}",
        display_name=f"Player {user_id}",
    )


def player(
    user_id: int,
    season: str,
    *,
    rating: int,
    games: int,
    wins: int,
    draws: int,
    losses: int,
    updated_at: datetime,
) -> PvPPlayerRow:
    return PvPPlayerRow(
        user_id=user_id,
        season=season,
        rating=rating,
        games=games,
        wins=wins,
        draws=draws,
        losses=losses,
        updated_at=updated_at,
    )


def match(
    match_id: str,
    season: str,
    pro_user_id: int,
    con_user_id: int,
    *,
    winner_user_id: int | None,
    pro_before: int,
    pro_after: int,
    con_before: int,
    con_after: int,
    ended_at: datetime,
    pro_scores: dict[str, float] | None = None,
    con_scores: dict[str, float] | None = None,
    rated: bool = True,
) -> PvPMatchRow:
    if winner_user_id == pro_user_id:
        outcome = "pro"
    elif winner_user_id == con_user_id:
        outcome = "con"
    else:
        outcome = "draw"
    return PvPMatchRow(
        match_id=match_id,
        season=season,
        topic="Тестовая тема",
        pair_key=f"{min(pro_user_id, con_user_id)}:{max(pro_user_id, con_user_id)}",
        pro_user_id=pro_user_id,
        con_user_id=con_user_id,
        winner_user_id=winner_user_id,
        outcome=outcome,
        rated=rated,
        unrated_reason=None,
        pro_rating_before=pro_before,
        pro_rating_after=pro_after,
        con_rating_before=con_before,
        con_rating_after=con_after,
        pro_scores=pro_scores or {"logic": 7, "evidence": 7, "rebuttal": 7},
        con_scores=con_scores or {"logic": 7, "evidence": 7, "rebuttal": 7},
        reason="Тестовый вердикт",
        transcript=[],
        started_at=ended_at - timedelta(minutes=10),
        ended_at=ended_at,
    )


@pytest.mark.asyncio
async def test_personal_record_book_uses_cross_season_matches() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = PvPRecordRepository(database.sessions)
    base = datetime(2026, 8, 1, 10, tzinfo=UTC)

    async with database.sessions.begin() as db:
        db.add_all([profile(1), profile(2), profile(3)])
        db.add_all(
            [
                match(
                    "m1",
                    "season-a",
                    1,
                    2,
                    winner_user_id=1,
                    pro_before=1000,
                    pro_after=1016,
                    con_before=1000,
                    con_after=984,
                    ended_at=base,
                    pro_scores={"logic": 8, "evidence": 8, "rebuttal": 8},
                ),
                match(
                    "m2",
                    "season-a",
                    2,
                    1,
                    winner_user_id=1,
                    pro_before=1000,
                    pro_after=980,
                    con_before=1016,
                    con_after=1036,
                    ended_at=base + timedelta(hours=1),
                    con_scores={"logic": 9, "evidence": 9, "rebuttal": 9},
                ),
                match(
                    "m3",
                    "season-a",
                    1,
                    3,
                    winner_user_id=3,
                    pro_before=1036,
                    pro_after=1020,
                    con_before=1000,
                    con_after=1016,
                    ended_at=base + timedelta(hours=2),
                ),
                match(
                    "m4",
                    "season-b",
                    1,
                    2,
                    winner_user_id=1,
                    pro_before=900,
                    pro_after=924,
                    con_before=1120,
                    con_after=1096,
                    ended_at=base + timedelta(days=1),
                    pro_scores={"logic": 9, "evidence": 8, "rebuttal": 9},
                ),
                match(
                    "m5",
                    "season-b",
                    3,
                    1,
                    winner_user_id=None,
                    pro_before=1016,
                    pro_after=1016,
                    con_before=924,
                    con_after=924,
                    ended_at=base + timedelta(days=1, hours=1),
                    con_scores={"logic": 11, "evidence": 1, "rebuttal": 1},
                ),
            ]
        )

    book = await repository.personal(1)

    assert book is not None
    assert book.seasons == 2
    assert book.total_matches == 5
    assert (book.wins, book.draws, book.losses) == (3, 1, 1)
    assert book.win_rate == 60.0
    assert book.distinct_opponents == 2
    assert book.longest_win_streak is not None
    assert (book.longest_win_streak.wins, book.longest_win_streak.season) == (
        2,
        "season-a",
    )
    assert book.best_rating_gain is not None
    assert (book.best_rating_gain.value, book.best_rating_gain.match_id) == (24.0, "m4")
    assert book.biggest_upset is not None
    assert (book.biggest_upset.value, book.biggest_upset.match_id) == (220.0, "m4")
    assert book.highest_score is not None
    assert (book.highest_score.value, book.highest_score.match_id) == (27.0, "m2")
    assert book.favorite_rival is not None
    assert (book.favorite_rival.opponent_user_id, book.favorite_rival.matches) == (2, 3)
    await database.close()


@pytest.mark.asyncio
async def test_season_record_book_is_deterministic() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = PvPRecordRepository(database.sessions)
    base = datetime(2026, 8, 2, 8, tzinfo=UTC)
    season = "season-x"

    async with database.sessions.begin() as db:
        db.add_all([profile(1), profile(2), profile(3)])
        db.add_all(
            [
                player(
                    1,
                    season,
                    rating=1100,
                    games=4,
                    wins=3,
                    draws=0,
                    losses=1,
                    updated_at=base,
                ),
                player(
                    2,
                    season,
                    rating=1050,
                    games=5,
                    wins=2,
                    draws=0,
                    losses=3,
                    updated_at=base + timedelta(minutes=1),
                ),
                player(
                    3,
                    season,
                    rating=1000,
                    games=3,
                    wins=1,
                    draws=0,
                    losses=2,
                    updated_at=base + timedelta(minutes=2),
                ),
            ]
        )
        db.add_all(
            [
                match(
                    "s1",
                    season,
                    1,
                    2,
                    winner_user_id=1,
                    pro_before=900,
                    pro_after=924,
                    con_before=1100,
                    con_after=1076,
                    ended_at=base,
                ),
                match(
                    "s2",
                    season,
                    2,
                    1,
                    winner_user_id=1,
                    pro_before=1076,
                    pro_after=1060,
                    con_before=924,
                    con_after=940,
                    ended_at=base + timedelta(hours=1),
                ),
                match(
                    "s3",
                    season,
                    1,
                    2,
                    winner_user_id=2,
                    pro_before=940,
                    pro_after=924,
                    con_before=1060,
                    con_after=1076,
                    ended_at=base + timedelta(hours=2),
                ),
                match(
                    "s4",
                    season,
                    3,
                    2,
                    winner_user_id=3,
                    pro_before=1000,
                    pro_after=1016,
                    con_before=1076,
                    con_after=1060,
                    ended_at=base + timedelta(hours=3),
                ),
            ]
        )

    book = await repository.season(season)

    assert book is not None
    assert (book.total_players, book.total_matches) == (3, 4)
    assert book.most_wins is not None
    assert (book.most_wins.user_id, book.most_wins.value) == (1, 3)
    assert book.most_games is not None
    assert (book.most_games.user_id, book.most_games.value) == (2, 5)
    assert book.longest_win_streak is not None
    assert (book.longest_win_streak.user_id, book.longest_win_streak.value) == (1, 2)
    assert book.biggest_upset is not None
    assert (
        book.biggest_upset.winner_user_id,
        book.biggest_upset.loser_user_id,
        book.biggest_upset.elo_gap,
    ) == (1, 2, 200)
    assert book.busiest_rivalry is not None
    assert (
        book.busiest_rivalry.first_user_id,
        book.busiest_rivalry.second_user_id,
        book.busiest_rivalry.matches,
    ) == (1, 2, 3)
    assert await repository.season("unknown") is None
    await database.close()


def test_score_total_rejects_invalid_payloads() -> None:
    assert PvPRecordRepository._score_total(
        {"logic": 8, "evidence": 7.5, "rebuttal": 9}
    ) == 24.5
    assert PvPRecordRepository._score_total(
        {"logic": True, "evidence": 7, "rebuttal": 9}
    ) is None
    assert PvPRecordRepository._score_total(
        {"logic": 11, "evidence": 7, "rebuttal": 9}
    ) is None
