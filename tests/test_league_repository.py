import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.database import Database, PvPMatchRow, PvPPlayerRow, UserProfileRow
from bot.league_repository import LeagueRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


async def add_player(
    database: Database,
    *,
    user_id: int,
    rating: int,
    games: int,
    wins: int,
    draws: int,
    losses: int,
    updated_at: datetime,
) -> None:
    async with database.sessions.begin() as db:
        db.add(
            UserProfileRow(
                user_id=user_id,
                username=f"user{user_id}",
                display_name=f"User {user_id}",
            )
        )
        db.add(
            PvPPlayerRow(
                user_id=user_id,
                season="season-1",
                rating=rating,
                games=games,
                wins=wins,
                draws=draws,
                losses=losses,
                updated_at=updated_at,
            )
        )


async def add_match(
    database: Database,
    *,
    match_id: str,
    pro_user_id: int,
    con_user_id: int,
    winner_user_id: int | None,
    ended_at: datetime,
    rated: bool,
    pro_before: int,
    pro_after: int,
    con_before: int,
    con_after: int,
) -> None:
    async with database.sessions.begin() as db:
        db.add(
            PvPMatchRow(
                match_id=match_id,
                season="season-1",
                topic=f"Topic {match_id}",
                pair_key=f"{min(pro_user_id, con_user_id)}:{max(pro_user_id, con_user_id)}",
                pro_user_id=pro_user_id,
                con_user_id=con_user_id,
                winner_user_id=winner_user_id,
                outcome="draw" if winner_user_id is None else "judged",
                rated=rated,
                unrated_reason=None if rated else "test",
                pro_rating_before=pro_before,
                pro_rating_after=pro_after,
                con_rating_before=con_before,
                con_rating_after=con_after,
                pro_scores={},
                con_scores={},
                reason="Test",
                transcript=[],
                started_at=ended_at - timedelta(minutes=10),
                ended_at=ended_at,
            )
        )


@pytest.mark.asyncio
async def test_player_view_includes_rank_form_and_recent_delta() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    now = datetime(2026, 8, 2, 8, tzinfo=UTC)
    await add_player(
        database,
        user_id=1,
        rating=1_120,
        games=6,
        wins=4,
        draws=1,
        losses=1,
        updated_at=now,
    )
    await add_player(
        database,
        user_id=2,
        rating=1_180,
        games=4,
        wins=3,
        draws=0,
        losses=1,
        updated_at=now,
    )
    await add_player(
        database,
        user_id=3,
        rating=1_120,
        games=7,
        wins=4,
        draws=1,
        losses=2,
        updated_at=now,
    )
    await add_match(
        database,
        match_id="a",
        pro_user_id=1,
        con_user_id=2,
        winner_user_id=1,
        ended_at=now - timedelta(days=3),
        rated=True,
        pro_before=1_000,
        pro_after=1_016,
        con_before=1_000,
        con_after=984,
    )
    await add_match(
        database,
        match_id="b",
        pro_user_id=3,
        con_user_id=1,
        winner_user_id=None,
        ended_at=now - timedelta(days=2),
        rated=False,
        pro_before=1_100,
        pro_after=1_100,
        con_before=1_016,
        con_after=1_016,
    )
    await add_match(
        database,
        match_id="c",
        pro_user_id=1,
        con_user_id=3,
        winner_user_id=3,
        ended_at=now - timedelta(days=1),
        rated=True,
        pro_before=1_132,
        pro_after=1_120,
        con_before=1_108,
        con_after=1_120,
    )
    repository = LeagueRepository(database.sessions)

    player = await repository.player(1, "season-1")

    assert player is not None
    assert player.rank == 3
    assert player.status.name == "Платина"
    assert player.recent_form == ("В", "Н", "П")
    assert player.recent_rating_delta == 4
    await database.close()


@pytest.mark.asyncio
async def test_top_and_distribution_include_placement_players() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    now = datetime(2026, 8, 2, 8, tzinfo=UTC)
    await add_player(
        database,
        user_id=1,
        rating=1_120,
        games=6,
        wins=4,
        draws=1,
        losses=1,
        updated_at=now,
    )
    await add_player(
        database,
        user_id=2,
        rating=1_180,
        games=4,
        wins=3,
        draws=0,
        losses=1,
        updated_at=now,
    )
    await add_player(
        database,
        user_id=3,
        rating=1_120,
        games=7,
        wins=4,
        draws=1,
        losses=2,
        updated_at=now,
    )
    repository = LeagueRepository(database.sessions)

    top = await repository.top("season-1")
    distribution = await repository.distribution("season-1")
    by_key = {entry.key: entry.players for entry in distribution.entries}

    assert [entry.user_id for entry in top] == [2, 3, 1]
    assert top[0].status.is_placement is True
    assert distribution.total_players == 3
    assert by_key["placement"] == 1
    assert by_key["platinum"] == 2
    await database.close()
