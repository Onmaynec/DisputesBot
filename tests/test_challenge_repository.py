import importlib.util
from datetime import UTC, datetime, timedelta

import pytest

from bot.challenge_database import PvPChallengeRow
from bot.challenge_models import (
    ChallengeBlockedError,
    ChallengeStatus,
    ChallengeUnavailableError,
)
from bot.challenge_repository import ChallengeRepository
from bot.database import Database, PvPBlockRow, UserProfileRow
from bot.pvp_models import PvPUser

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


def user(user_id: int) -> PvPUser:
    return PvPUser(
        user_id=user_id,
        username=f"user{user_id}",
        display_name=f"User {user_id}",
    )


@pytest.mark.asyncio
async def test_create_is_idempotent_for_pair_and_lists_inbox() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = ChallengeRepository(database.sessions, ttl_hours=24)
    await database.create_all_for_tests()
    now = datetime(2026, 8, 2, 9, tzinfo=UTC)

    created, challenge = await repository.create(
        user(1),
        user(2),
        season="season-1",
        topic="Удалённая работа лучше офиса",
        now=now,
    )
    duplicate_created, duplicate = await repository.create(
        user(2),
        user(1),
        season="season-1",
        topic="Другая тема",
        now=now + timedelta(minutes=1),
    )
    first_inbox = await repository.inbox(1, "season-1", now=now)
    second_inbox = await repository.inbox(2, "season-1", now=now)

    assert created is True
    assert duplicate_created is False
    assert duplicate.challenge_id == challenge.challenge_id
    assert first_inbox.outgoing == (challenge,)
    assert second_inbox.incoming == (challenge,)
    assert challenge.status is ChallengeStatus.PENDING
    assert challenge.expires_at == now + timedelta(hours=24)
    await database.close()


@pytest.mark.asyncio
async def test_accept_reservation_release_and_completion() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = ChallengeRepository(database.sessions)
    await database.create_all_for_tests()
    now = datetime(2026, 8, 2, 9, tzinfo=UTC)
    _, challenge = await repository.create(
        user(1),
        user(2),
        season="season-1",
        topic="Тестовый вызов",
        now=now,
    )

    claimed = await repository.claim_accept(
        challenge.challenge_id,
        2,
        now=now + timedelta(minutes=1),
    )
    assert claimed.status is ChallengeStatus.ACCEPTING

    await repository.release_accept(
        challenge.challenge_id,
        now=now + timedelta(minutes=2),
    )
    claimed_again = await repository.claim_accept(
        challenge.challenge_id,
        2,
        now=now + timedelta(minutes=3),
    )
    await repository.complete_accept(
        challenge.challenge_id,
        "match-1",
        now=now + timedelta(minutes=4),
    )

    assert claimed_again.status is ChallengeStatus.ACCEPTING
    assert (await repository.inbox(2, "season-1", now=now)).incoming == ()
    with pytest.raises(ChallengeUnavailableError):
        await repository.claim_accept(challenge.challenge_id, 2, now=now)
    async with database.sessions() as db:
        stored = await db.get(PvPChallengeRow, challenge.challenge_id)
    assert stored is not None
    assert stored.status == ChallengeStatus.ACCEPTED.value
    assert stored.match_id == "match-1"
    await database.close()


@pytest.mark.asyncio
async def test_blocklist_and_expiration_are_enforced() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = ChallengeRepository(database.sessions, ttl_hours=1)
    await database.create_all_for_tests()
    now = datetime(2026, 8, 2, 9, tzinfo=UTC)
    _, challenge = await repository.create(
        user(1),
        user(2),
        season="season-1",
        topic="Вызов с коротким сроком",
        now=now,
    )

    expired = await repository.inbox(2, "season-1", now=now + timedelta(hours=2))
    assert expired.incoming == ()
    async with database.sessions() as db:
        stored = await db.get(PvPChallengeRow, challenge.challenge_id)
    assert stored is not None
    assert stored.status == ChallengeStatus.EXPIRED.value

    async with database.sessions.begin() as db:
        db.add(
            PvPBlockRow(
                blocker_id=1,
                blocked_id=2,
                blocked_label="User 2",
            )
        )
    with pytest.raises(ChallengeBlockedError):
        await repository.create(
            user(1),
            user(2),
            season="season-2",
            topic="Заблокированный вызов",
            now=now,
        )
    await database.close()


@pytest.mark.asyncio
async def test_decline_cancel_and_delete_user_data() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    repository = ChallengeRepository(database.sessions)
    await database.create_all_for_tests()
    now = datetime(2026, 8, 2, 9, tzinfo=UTC)

    _, declined = await repository.create(
        user(1),
        user(2),
        season="season-1",
        topic="Отклоняемый вызов",
        now=now,
    )
    resolved = await repository.decline(declined.challenge_id, 2, now=now)
    assert resolved.status is ChallengeStatus.DECLINED

    _, cancelled = await repository.create(
        user(1),
        user(3),
        season="season-1",
        topic="Отменяемый вызов",
        now=now,
    )
    resolved_cancel = await repository.cancel(cancelled.challenge_id, 1, now=now)
    assert resolved_cancel.status is ChallengeStatus.CANCELLED

    _, pending = await repository.create(
        user(1),
        user(4),
        season="season-1",
        topic="Удаляемый вызов",
        now=now,
    )
    await repository.delete_user_data(1)
    async with database.sessions() as db:
        assert await db.get(PvPChallengeRow, pending.challenge_id) is None
        assert await db.get(UserProfileRow, 1) is not None
    await database.close()
