from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .league_models import DEFAULT_PLACEMENT_GAMES, league_status
from .pvp_invites import _identity, notify_match_started
from .pvp_models import PvPQueueEntry, PvPQueueMode
from .pvp_repository import PvPRepository
from .pvp_store import PvPBusyError
from .ranked_pvp_store import RankedPvPStore
from .storage import SessionStore

router = Router(name="pvp-queue")


def _topic_or_error(command: CommandObject, settings: Settings) -> tuple[str | None, str | None]:
    topic = (command.args or "").strip()
    if not topic:
        return None, "Укажите тему после команды."
    if len(topic) > settings.max_topic_chars:
        return None, f"Тема длиннее {settings.max_topic_chars} символов."
    return topic, None


async def _join_queue(
    message: Message,
    entry: PvPQueueEntry,
    pvp_store: RankedPvPStore,
    store: SessionStore,
) -> None:
    if await store.get_session(entry.participant.user_id) is not None:
        await message.answer("Сначала завершите одиночный спор командой /cancel.")
        return
    try:
        match = await pvp_store.join_queue(entry)
    except PvPBusyError as exc:
        await message.answer(f"Очередь недоступна: {exc}")
        return
    if match is None:
        if entry.mode is PvPQueueMode.RANKED:
            gap = pvp_store.ranked_search_gap(entry)
            status = league_status(entry.rating, entry.games)
            league_text = (
                f"калибровка {entry.games}/{DEFAULT_PLACEMENT_GAMES}"
                if status.is_placement
                else f"{status.league.icon} {status.league.name}"
            )
            await message.answer(
                "🎯 Вы добавлены в рейтинговую очередь.\n"
                f"Elo: {entry.rating} · {league_text}\n"
                f"Текущий диапазон: ±{gap} Elo.\n"
                "Диапазон постепенно расширяется во время ожидания.\n"
                "Статус: /queue_status · выйти: /leave_queue"
            )
        else:
            await message.answer(
                "🔎 Вы добавлены в обычную очередь. Бот сообщит, когда найдётся соперник.\n"
                "Статус: /queue_status · выйти: /leave_queue"
            )
        return
    if (
        await store.get_session(match.pro.user_id) is not None
        or await store.get_session(match.con.user_id) is not None
    ):
        await pvp_store.cancel_match(match)
        await message.answer("Подбор отменён: один из участников начал одиночный спор.")
        return
    await notify_match_started(message.bot, match)


@router.message(Command("queue"))
async def queue_command(
    message: Message,
    command: CommandObject,
    pvp_store: RankedPvPStore,
    store: SessionStore,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    topic, error = _topic_or_error(command, settings)
    if error is not None:
        await message.answer(f"{error}\nПример: /queue Социальные сети приносят больше вреда")
        return
    assert topic is not None
    await _join_queue(
        message,
        PvPQueueEntry(
            participant=_identity(message.from_user),
            topic=topic,
            season=settings.pvp_season,
        ),
        pvp_store,
        store,
    )


@router.message(Command("ranked_queue"))
async def ranked_queue_command(
    message: Message,
    command: CommandObject,
    pvp_store: RankedPvPStore,
    pvp_repository: PvPRepository,
    store: SessionStore,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    topic, error = _topic_or_error(command, settings)
    if error is not None:
        await message.answer(
            f"{error}\nПример: /ranked_queue Искусственный интеллект полезен обществу"
        )
        return
    assert topic is not None
    rating = await pvp_repository.rating(message.from_user.id, settings.pvp_season)
    await _join_queue(
        message,
        PvPQueueEntry(
            participant=_identity(message.from_user),
            topic=topic,
            season=settings.pvp_season,
            mode=PvPQueueMode.RANKED,
            rating=rating.rating if rating is not None else 1000,
            games=rating.games if rating is not None else 0,
        ),
        pvp_store,
        store,
    )


@router.message(Command("queue_status"))
async def queue_status_command(message: Message, pvp_store: RankedPvPStore) -> None:
    if message.from_user is None:
        return
    entry = await pvp_store.get_queue_entry(message.from_user.id)
    if entry is None:
        await message.answer("Вас нет в PvP-очереди.")
        return
    queued_at = entry.queued_at
    if queued_at.tzinfo is None:
        queued_at = queued_at.replace(tzinfo=UTC)
    waited_seconds = max(0, int((datetime.now(UTC) - queued_at).total_seconds()))
    waited_minutes = waited_seconds // 60
    if entry.mode is PvPQueueMode.RANKED:
        gap = pvp_store.ranked_search_gap(entry)
        status = league_status(entry.rating, entry.games)
        league_text = (
            f"калибровка {entry.games}/{DEFAULT_PLACEMENT_GAMES}"
            if status.is_placement
            else f"{status.league.icon} {status.league.name}"
        )
        await message.answer(
            "🎯 Рейтинговая очередь\n"
            f"Elo: {entry.rating} · {league_text}\n"
            f"Диапазон: ±{gap} Elo\n"
            f"Ожидание: {waited_minutes} мин.\n"
            f"Тема: {entry.topic}\n\n"
            "Выйти: /leave_queue"
        )
        return
    await message.answer(
        "🔎 Обычная очередь\n"
        f"Ожидание: {waited_minutes} мин.\n"
        f"Тема: {entry.topic}\n\n"
        "Выйти: /leave_queue"
    )


@router.message(Command("leave_queue"))
async def leave_queue_command(message: Message, pvp_store: RankedPvPStore) -> None:
    if message.from_user is None:
        return
    try:
        removed = await pvp_store.leave_queue(message.from_user.id)
    except PvPBusyError:
        await message.answer("Очередь обновляется. Повторите команду.")
        return
    await message.answer("✅ Вы вышли из очереди." if removed else "Вас не было в очереди.")
