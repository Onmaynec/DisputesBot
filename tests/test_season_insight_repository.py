import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.database import Database, PvPMatchRow, PvPPlayerRow, UserProfileRow
from bot.ranked_reward_database import PvPRankedRewardClaimRow
from bot.season_insight_repository import SeasonInsightRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is installed in CI and development dependencies",
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
    rated: bool = True,
    pro_scores: dict[str, int] | None = None,
    con_scores: dict[str, int] | None = None,
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
        rated=rated,
        unrated_reason=None if rated else "pair limit",
        pro_rating_before=pro_before,
        pro_rating_after=pro_after,
        con_rating_before=con_before,
        con_rating_after=con_after,
        pro_scores=pro_scores or {},
        con_scores=con_scores or {},
        reason=f"Reason {match_id}",
        transcript=[],
        started_at=ended_at - timedelta(minutes=10),
        ended_at=ended_at,
    )


async def seed_database(database: Database) -> None:
    now = datetime.now(UTC)
    async with database.sessions.begin() as db:
        db.add_all(
            [
                UserProfileRow(user_id=1, username="one", display_name="User One"),
                UserProfileRow(user_id=2, username="two", display_name="User Two"),
                UserProfileRow(user_id=3, username="three", display_name="User Three"),
                PvPPlayerRow(
                    user_id=1,
                    season="season-1",
                    rating=1040,
                    games=4,
                    wins=2,
                    draws=1,
                    losses=1,
                    updated_at=now,
                ),
                PvPPlayerRow(
                    user_id=2,
                    season="season-1",
                    rating=1060,
                    games=4,
                    wins=3,
                    draws=0,
                    losses=1,
                    updated_at=now,
                ),
                PvPPlayerRow(
                    user_id=3,
                    season="season-1",
                    rating=990,
                    games=3,
                    wins=1,
                    draws=1,
                    losses=1,
                    updated_at=now,
                ),
                PvPPlayerRow(
                    user_id=1,
                    season="season-2",
                    rating=1120,
                    games=6,
                    wins=4,
                    draws=1,
                    losses=1,
                    updated_at=now + timedelta(days=1),
                ),
                PvPPlayerRow(
                    user_id=2,
                    season="season-2",
                    rating=1080,
                    games=6,
                    wins=3,
                    draws=1,
                    losses=2,
                    updated_at=now + timedelta(days=1),
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
                    pro_after=1012,
                    con_before=1000,
                    con_after=988,
                    pro_scores={"logic": 8, "evidence": 7, "rebuttal": 6},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
                match_row(
                    "s1-m2",
                    season="season-1",
                    ended_at=now + timedelta(minutes=1),
                    pro_user_id=2,
                    con_user_id=1,
                    winner_user_id=1,
                    pro_before=988,
                    pro_after=970,
                    con_before=1012,
                    con_after=1055,
                    pro_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                    con_scores={"logic": 7, "evidence": 8, "rebuttal": 7},
                ),
                match_row(
                    "s1-m3",
                    season="season-1",
                    ended_at=now + timedelta(minutes=2),
                    pro_user_id=1,
                    con_user_id=3,
                    winner_user_id=None,
                    pro_before=1055,
                    pro_after=1055,
                    con_before=1000,
                    con_after=1000,
                    rated=False,
                    pro_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
                match_row(
                    "s1-m4",
                    season="season-1",
                    ended_at=now + timedelta(minutes=3),
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=2,
                    pro_before=1055,
                    pro_after=1040,
                    con_before=970,
                    con_after=985,
                    pro_scores={"logic": 5, "evidence": 5, "rebuttal": 5},
                    con_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
                ),
                match_row(
                    "s2-m1",
                    season="season-2",
                    ended_at=now + timedelta(days=1),
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=1,
                    pro_before=1000,
                    pro_after=1030,
                    con_before=1000,
                    con_after=970,
                    pro_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
                match_row(
                    "s2-m2",
                    season="season-2",
                    ended_at=now + timedelta(days=1, minutes=1),
                    pro_user_id=2,
                    con_user_id=1,
                    winner_user_id=1,
                    pro_before=970,
                    pro_after=950,
                    con_before=1030,
                    con_after=1070,
                    pro_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                    con_scores={"logic": 8, "evidence": 8, "rebuttal": 8},
                ),
                match_row(
                    "s2-m3",
                    season="season-2",
                    ended_at=now + timedelta(days=1, minutes=2),
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=1,
                    pro_before=1070,
                    pro_after=1150,
                    con_before=950,
                    con_after=920,
                    pro_scores={"logic": 9, "evidence": 8, "rebuttal": 8},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
                match_row(
                    "s2-m4",
                    season="season-2",
                    ended_at=now + timedelta(days=1, minutes=3),
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=None,
                    pro_before=1150,
                    pro_after=1150,
                    con_before=920,
                    con_after=920,
                    pro_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
                    con_scores={"logic": 7, "evidence": 7, "rebuttal": 7},
                ),
                match_row(
                    "s2-m5",
                    season="season-2",
                    ended_at=now + timedelta(days=1, minutes=4),
                    pro_user_id=2,
                    con_user_id=1,
                    winner_user_id=2,
                    pro_before=920,
                    pro_after=940,
                    con_before=1150,
                    con_after=1130,
                    pro_scores={"logic": 8, "evidence": 8, "rebuttal": 8},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
                match_row(
                    "s2-m6",
                    season="season-2",
                    ended_at=now + timedelta(days=1, minutes=5),
                    pro_user_id=1,
                    con_user_id=2,
                    winner_user_id=1,
                    pro_before=1130,
                    pro_after=1120,
                    con_before=940,
                    con_after=950,
                    rated=False,
                    pro_scores={"logic": 8, "evidence": 7, "rebuttal": 8},
                    con_scores={"logic": 6, "evidence": 6, "rebuttal": 6},
                ),
            ]
        )
        db.add_all(
            [
                PvPRankedRewardClaimRow(
                    user_id=1,
                    season="season-1",
                    league_id="bronze",
                    reward_tokens=15,
                    claimed_rating=1040,
                    claimed_at=now,
                ),
                PvPRankedRewardClaimRow(
                    user_id=1,
                    season="season-1",
                    league_id="silver",
                    reward_tokens=25,
                    claimed_rating=1040,
                    claimed_at=now,
                ),
            ]
        )


@pytest.mark.asyncio
async def test_recap_combines_rating_matches_skills_and_rewards() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await seed_database(database)
    repository = SeasonInsightRepository(database.sessions)

    recap = await repository.recap(1, "season-1")

    assert recap is not None
    assert recap.rank == 2
    assert recap.total_players == 3
    assert recap.starting_rating == 1000
    assert recap.rating == 1040
    assert recap.peak_rating == 1055
    assert recap.net_rating == 40
    assert recap.rated_matches == 3
    assert recap.unrated_matches == 1
    assert recap.unique_opponents == 2
    assert recap.longest_win_streak == 2
    assert recap.favorite_opponent_id == 2
    assert recap.favorite_opponent_name == "User Two"
    assert recap.favorite_opponent_matches == 3
    assert recap.claimed_milestones == 2
    assert recap.claimed_tokens == 40
    assert recap.skills is not None
    assert recap.skills.logic == pytest.approx(6.5)
    assert recap.skills.evidence == pytest.approx(6.5)
    assert recap.skills.rebuttal == pytest.approx(6.0)
    await database.close()


@pytest.mark.asyncio
async def test_compare_recent_and_records_use_multi_season_data() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await seed_database(database)
    repository = SeasonInsightRepository(database.sessions)

    comparison = await repository.compare_recent(1)
    records = await repository.records(1)

    assert comparison is not None
    assert comparison.older.season == "season-1"
    assert comparison.newer.season == "season-2"
    assert comparison.rating_delta == 80
    assert comparison.peak_delta == 95
    assert comparison.games_delta == 2
    assert comparison.streak_delta == 1

    assert records is not None
    assert records.seasons_count == 2
    assert records.highest_final.season == "season-2"
    assert records.highest_peak.peak_rating == 1150
    assert records.most_wins.wins == 4
    assert records.most_games.games == 6
    assert records.best_win_rate.season == "season-2"
    assert records.biggest_gain.net_rating == 120
    assert records.longest_streak.longest_win_streak == 3
    await database.close()


@pytest.mark.asyncio
async def test_invalid_or_missing_seasons_are_rejected() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    await seed_database(database)
    repository = SeasonInsightRepository(database.sessions)

    assert await repository.recap(1, "unknown") is None
    assert await repository.recap(1, "season with spaces") is None
    assert await repository.compare(1, "season-1", "season-1") is None
    assert await repository.compare(3, "season-1", "season-2") is None
    await database.close()


def test_repository_validates_limits() -> None:
    with pytest.raises(ValueError):
        SeasonInsightRepository(None, max_seasons=0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        SeasonInsightRepository(None, max_seasons=51)  # type: ignore[arg-type]
