import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.database import (
    Database,
    PvPBlockRow,
    PvPMatchRow,
    PvPPlayerRow,
    PvPProgressionRow,
    UserProfileRow,
)
from bot.pvp_models import PvPUser
from bot.social_models import ProfileLookupStatus, ProfileVisibility
from bot.social_repository import SocialRepository

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


async def add_profile(
    database: Database,
    user_id: int,
    *,
    rating: int = 1000,
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
                games=3,
                wins=1,
                draws=1,
                losses=1,
            )
        )
        db.add(
            PvPProgressionRow(
                user_id=user_id,
                season="season-1",
                tokens=200,
                season_points=300,
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
    pro_before: int = 1000,
    pro_after: int = 1000,
    con_before: int = 1000,
    con_after: int = 1000,
    rated: bool = True,
    topic: str = "Тестовая тема",
) -> None:
    async with database.sessions.begin() as db:
        db.add(
            PvPMatchRow(
                match_id=match_id,
                season="season-1",
                topic=topic,
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
                reason="Тест",
                transcript=[],
                started_at=ended_at - timedelta(minutes=10),
                ended_at=ended_at,
            )
        )


@pytest.mark.asyncio
async def test_profiles_are_private_by_default_and_block_aware() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = SocialRepository(database.sessions)
    await database.create_all_for_tests()
    await add_profile(database, 1, rating=1010)
    await add_profile(database, 2, rating=1040)
    requester = PvPUser(user_id=1, username="user1", display_name="User 1")
    target = PvPUser(user_id=2, username="user2", display_name="User 2")

    own = await repository.profile(requester, 1, "season-1")
    hidden = await repository.profile(requester, 2, "season-1")
    await repository.set_visibility(target, ProfileVisibility.PUBLIC)
    visible = await repository.profile(requester, 2, "season-1")

    assert own.status is ProfileLookupStatus.FOUND
    assert own.profile is not None
    assert own.profile.is_public is False
    assert hidden.status is ProfileLookupStatus.PRIVATE
    assert visible.status is ProfileLookupStatus.FOUND
    assert visible.profile is not None
    assert visible.profile.rating == 1040
    assert visible.profile.rank == 1

    async with database.sessions.begin() as db:
        db.add(PvPBlockRow(blocker_id=2, blocked_id=1, blocked_label="User 1"))
    blocked = await repository.profile(requester, 2, "season-1")
    assert blocked.status is ProfileLookupStatus.BLOCKED
    await database.close()


@pytest.mark.asyncio
async def test_rivals_and_head_to_head_use_only_shared_matches() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = SocialRepository(database.sessions)
    await database.create_all_for_tests()
    await add_profile(database, 1)
    await add_profile(database, 2)
    await add_profile(database, 3)
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)

    await add_match(
        database,
        match_id="rival-a",
        pro_user_id=1,
        con_user_id=2,
        winner_user_id=1,
        ended_at=now - timedelta(days=2),
        pro_after=1016,
        con_after=984,
        topic="Первая тема",
    )
    await add_match(
        database,
        match_id="rival-b",
        pro_user_id=2,
        con_user_id=1,
        winner_user_id=2,
        ended_at=now - timedelta(days=1),
        pro_before=984,
        pro_after=1000,
        con_before=1016,
        con_after=1000,
        topic="Вторая тема",
    )
    await add_match(
        database,
        match_id="rival-c",
        pro_user_id=1,
        con_user_id=3,
        winner_user_id=None,
        ended_at=now,
        rated=False,
        topic="Третья тема",
    )

    rivals = await repository.rivals(1, "season-1")
    duel = await repository.head_to_head(1, 2, "season-1")

    assert [item.opponent_id for item in rivals] == [2, 3]
    assert (rivals[0].matches, rivals[0].wins, rivals[0].losses) == (2, 1, 1)
    assert rivals[0].rating_delta == 0
    assert rivals[1].draws == 1
    assert rivals[1].rated_matches == 0
    assert duel is not None
    assert (duel.matches, duel.wins, duel.draws, duel.losses) == (2, 1, 0, 1)
    assert duel.rating_delta == 0
    assert duel.current_win_streak == 0
    assert duel.recent_topics == ("Вторая тема", "Первая тема")
    await database.close()


@pytest.mark.asyncio
async def test_visibility_setting_can_be_deleted() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = SocialRepository(database.sessions)
    await database.create_all_for_tests()
    user = PvPUser(user_id=7, username="user7", display_name="User 7")

    await repository.set_visibility(user, ProfileVisibility.PUBLIC)
    assert await repository.visibility(7) is ProfileVisibility.PUBLIC
    await repository.delete_user_data(7)
    assert await repository.visibility(7) is ProfileVisibility.PRIVATE
    await database.close()
