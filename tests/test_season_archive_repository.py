import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.database import Database, PvPMatchRow, PvPPlayerRow, UserProfileRow
from bot.season_archive_repository import SeasonArchiveRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


def match_row(
    match_id: str,
    *,
    season: str,
    ended_at: datetime,
    pro_user_id: int,
    con_user_id: int,
    winner_user_id: int | None,
    pro_before: int,
    pro_after: int,
    con_before: int,
    con_after: int,
) -> PvPMatchRow:
    return PvPMatchRow(
        match_id=match_id,
        season=season,
        topic=f"Topic {match_id}",
        pair_key=f"{min(pro_user_id, con_user_id)}:{max(pro_user_id, con_user_id)}",
        pro_user_id=pro_user_id,
        con_user_id=con_user_id,
        winner_user_id=winner_user_id,
        outcome="draw" if winner_user_id is None else "judged",
        rated=True,
        unrated_reason=None,
        pro_rating_before=pro_before,
        pro_rating_after=pro_after,
        con_rating_before=con_before,
        con_rating_after=con_after,
        pro_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
        con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
        reason=f"Reason {match_id}",
        transcript=[],
        started_at=ended_at - timedelta(minutes=10),
        ended_at=ended_at,
    )


async def seed(database: Database) -> None:
    now = datetime.now(UTC)
    async with database.sessions.begin() as db:
        db.add_all(
            [
                UserProfileRow(user_id=1, username="one", display_name="Player One"),
                UserProfileRow(user_id=2, username="two", display_name="Player Two"),
                UserProfileRow(user_id=3, username="three", display_name="Player Three"),
            ]
        )
        db.add_all(
            [
                PvPPlayerRow(
                    user_id=1,
                    season="season-1",
                    rating=1100,
                    games=3,
                    wins=2,
                    draws=0,
                    losses=1,
                    updated_at=now,
                ),
                PvPPlayerRow(
                    user_id=2,
                    season="season-1",
                    rating=1080,
                    games=3,
                    wins=1,
                    draws=0,
                    losses=2,
                    updated_at=now + timedelta(seconds=1),
                ),
                PvPPlayerRow(
                    user_id=3,
                    season="season-1",
                    rating=900,
                    games=1,
                    wins=0,
                    draws=0,
                    losses=1,
                    updated_at=now + timedelta(seconds=2),
                ),
                PvPPlayerRow(
                    user_id=1,
                    season="season-2",
                    rating=1050,
                    games=2,
                    wins=1,
                    draws=1,
                    losses=0,
                    updated_at=now + timedelta(days=1),
                ),
                PvPPlayerRow(
                    user_id=2,
                    season="season-2",
                    rating=1150,
                    games=2,
                    wins=1,
                    draws=1,
                    losses=0,
                    updated_at=now + timedelta(days=1, seconds=1),
                ),
            ]
        )
        db.add_all(
            [
                match_row(
                    "s1-m1",
                    season="season-1",
                    ended_at=now,
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=1,
                    pro_before=1000,
                    pro_after=1040,
                    con_before=1000,
                    con_after=960,
                ),
                match_row(
                    "s1-m2",
                    season="season-1",
                    ended_at=now + timedelta(minutes=1),
                    pro_user_id=2,
                    con_user_id=1,
                    winner_user_id=1,
                    pro_before=960,
                    pro_after=920,
                    con_before=1040,
                    con_after=1120,
                ),
                match_row(
                    "s1-m3",
                    season="season-1",
                    ended_at=now + timedelta(minutes=2),
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=2,
                    pro_before=1120,
                    pro_after=1100,
                    con_before=920,
                    con_after=1080,
                ),
                match_row(
                    "s2-m1",
                    season="season-2",
                    ended_at=now + timedelta(days=1),
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=1,
                    pro_before=1000,
                    pro_after=1060,
                    con_before=1000,
                    con_after=1140,
                ),
                match_row(
                    "s2-m2",
                    season="season-2",
                    ended_at=now + timedelta(days=1, minutes=1),
                    pro_user_id=2,
                    con_user_id=1,
                    winner_user_id=None,
                    pro_before=1140,
                    pro_after=1150,
                    con_before=1060,
                    con_after=1050,
                ),
            ]
        )


@pytest.mark.asyncio
async def test_career_aggregates_seasons_rank_and_peak_rating() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await seed(database)
    repository = SeasonArchiveRepository(database.sessions)

    career = await repository.career(1)

    assert career is not None
    assert career.total_games == 5
    assert (career.total_wins, career.total_draws, career.total_losses) == (3, 1, 1)
    assert career.peak_rating == 1120
    assert career.seasons[0].season == "season-2"
    assert career.seasons[0].rank == 2
    assert career.seasons[1].rank == 1
    assert career.seasons[1].starting_rating == 1000
    assert career.seasons[1].peak_rating == 1120
    assert career.best_season.season == "season-1"
    assert await repository.career(999) is None
    await database.close()


@pytest.mark.asyncio
async def test_catalog_and_archive_use_stable_season_rankings() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await seed(database)
    repository = SeasonArchiveRepository(database.sessions)

    catalog = await repository.catalog()
    archive = await repository.archive("season-2")

    assert [entry.season for entry in catalog] == ["season-2", "season-1"]
    assert catalog[0].champion_user_id == 2
    assert catalog[0].champion_rating == 1150
    assert catalog[0].players == 2
    assert catalog[0].matches == 2
    assert archive is not None
    assert archive.total_players == 2
    assert archive.total_matches == 2
    assert [entry.user_id for entry in archive.standings] == [2, 1]
    assert await repository.archive("missing") is None
    assert await repository.archive("x" * 33) is None
    await database.close()


def test_repository_validates_limits() -> None:
    with pytest.raises(ValueError):
        SeasonArchiveRepository(None, max_seasons=0)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        SeasonArchiveRepository(None, max_seasons=51)  # type: ignore[arg-type]
