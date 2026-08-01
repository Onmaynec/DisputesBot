import importlib.util

import pytest

from bot.database import Database
from bot.models import Stance
from bot.moderation_models import ReportCategory, ReportStatus
from bot.moderation_repository import ModerationRepository
from bot.pvp_models import PvPMatch, PvPParticipant, PvPUser

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("aiosqlite") is None,
    reason="aiosqlite is not installed in the local sandbox",
)


@pytest.mark.asyncio
async def test_blocklist_is_bidirectional_for_matchmaking() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = ModerationRepository(database.sessions)

    created = await repository.block_user(
        PvPUser(user_id=1, display_name="One"),
        2,
        blocked_label="Two",
    )
    duplicate = await repository.block_user(
        PvPUser(user_id=1, display_name="One"),
        2,
        blocked_label="Two updated",
    )

    assert created
    assert not duplicate
    assert not await repository.pair_allowed(1, 2)
    assert not await repository.pair_allowed(2, 1)
    assert await repository.unblock_user(1, 2)
    assert await repository.pair_allowed(1, 2)
    await database.close()


@pytest.mark.asyncio
async def test_report_is_idempotent_and_audited() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all_for_tests()
    repository = ModerationRepository(database.sessions)
    match = PvPMatch(
        topic="Тема",
        season="s1",
        pro=PvPParticipant(user_id=1, display_name="One", stance=Stance.PRO),
        con=PvPParticipant(user_id=2, display_name="Two", stance=Stance.CON),
    )

    first, report = await repository.create_report(
        reporter_id=1,
        category=ReportCategory.SPAM,
        comment="Повторяющиеся сообщения",
        match=match,
    )
    second, same = await repository.create_report(
        reporter_id=1,
        category=ReportCategory.OTHER,
        comment="Дубликат",
        match=match,
    )
    changed, resolved = await repository.resolve_report(
        report.report_id,
        status=ReportStatus.RESOLVED,
        moderator_id=99,
        note="Проверено",
    )

    assert first
    assert not second
    assert same.report_id == report.report_id
    assert changed
    assert resolved is not None
    assert resolved.status is ReportStatus.RESOLVED
    assert resolved.moderator_id == 99
    await repository.anonymize_user(1)
    assert await repository.my_reports(1) == []
    await database.close()
