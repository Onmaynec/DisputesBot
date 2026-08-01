import pytest

from bot.pvp_models import PvPQueueEntry, PvPUser
from bot.pvp_store import PvPBusyError, PvPStore
from tests.fake_redis import FakeRedis


@pytest.mark.asyncio
async def test_pvp_store_restores_match_for_both_users() -> None:
    redis = FakeRedis()
    first_process = PvPStore(redis, prefix="test")
    match = await first_process.create_match(
        PvPUser(user_id=1, display_name="One"),
        PvPUser(user_id=2, display_name="Two"),
        topic="Тема",
        season="season-1",
        first_is_pro=True,
    )
    match.add_argument(1, "Аргумент")
    await first_process.save_match(match)

    second_process = PvPStore(redis, prefix="test")
    restored_one = await second_process.get_match_for_user(1)
    restored_two = await second_process.get_match_for_user(2)

    assert restored_one == restored_two
    assert restored_one is not None
    assert restored_one.match_id == match.match_id
    assert len(restored_one.arguments) == 1


@pytest.mark.asyncio
async def test_user_cannot_enter_two_active_matches() -> None:
    redis = FakeRedis()
    store = PvPStore(redis, prefix="test")
    user = PvPUser(user_id=1, display_name="One")
    await store.create_match(
        user,
        PvPUser(user_id=2, display_name="Two"),
        topic="Тема",
        season="season-1",
    )

    with pytest.raises(PvPBusyError):
        await store.create_match(
            user,
            PvPUser(user_id=3, display_name="Three"),
            topic="Другая тема",
            season="season-1",
        )


@pytest.mark.asyncio
async def test_matchmaking_pairs_different_users_and_removes_queue_entries() -> None:
    redis = FakeRedis()
    store = PvPStore(redis, prefix="test")
    first = PvPQueueEntry(
        participant=PvPUser(user_id=1, display_name="One"),
        topic="Первая тема",
        season="season-1",
    )
    second = PvPQueueEntry(
        participant=PvPUser(user_id=2, display_name="Two"),
        topic="Вторая тема",
        season="season-1",
    )

    assert await store.join_queue(first) is None
    match = await store.join_queue(second)

    assert match is not None
    assert {match.pro.user_id, match.con.user_id} == {1, 2}
    assert match.topic == "Первая тема"
    assert not await store.leave_queue(1)
    assert not await store.leave_queue(2)


@pytest.mark.asyncio
async def test_inviter_cannot_consume_invitation_by_validation_read() -> None:
    redis = FakeRedis()
    store = PvPStore(redis, prefix="test")
    invitation = await store.create_invitation(
        PvPUser(user_id=1, display_name="One"),
        topic="Тема",
        season="season-1",
    )

    inspected = await store.get_invitation(invitation.token)
    consumed = await store.consume_invitation(invitation.token)

    assert inspected == invitation
    assert consumed == invitation
    assert await store.consume_invitation(invitation.token) is None


@pytest.mark.asyncio
async def test_delete_user_data_removes_both_match_indexes() -> None:
    redis = FakeRedis()
    store = PvPStore(redis, prefix="test")
    match = await store.create_match(
        PvPUser(user_id=1, display_name="One"),
        PvPUser(user_id=2, display_name="Two"),
        topic="Тема",
        season="season-1",
    )

    await store.delete_user_data(1)

    assert await store.get_match(match.match_id) is None
    assert await store.get_match_for_user(1) is None
    assert await store.get_match_for_user(2) is None
