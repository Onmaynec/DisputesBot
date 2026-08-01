from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .pvp_invites import _identity, notify_match_started
from .pvp_models import PvPQueueEntry
from .pvp_store import PvPBusyError, PvPStore
from .storage import SessionStore

router = Router(name="pvp-queue")


@router.message(Command("queue"))
async def queue_command(
    message: Message,
    command: CommandObject,
    pvp_store: PvPStore,
    store: SessionStore,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    topic = (command.args or "").strip()
    if not topic:
        await message.answer("Укажите тему: /queue Социальные сети приносят больше вреда")
        return
    if len(topic) > settings.max_topic_chars:
        await message.answer(f"Тема длиннее {settings.max_topic_chars} символов.")
        return
    if await store.get_session(message.from_user.id) is not None:
        await message.answer("Сначала завершите одиночный спор командой /cancel.")
        return
    try:
        match = await pvp_store.join_queue(
            PvPQueueEntry(
                participant=_identity(message.from_user),
                topic=topic,
                season=settings.pvp_season,
            )
        )
    except PvPBusyError as exc:
        await message.answer(f"Очередь недоступна: {exc}")
        return
    if match is None:
        await message.answer(
            "🔎 Вы добавлены в очередь. Бот сообщит, когда найдётся соперник.\n"
            "Выйти: /leave_queue"
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


@router.message(Command("leave_queue"))
async def leave_queue_command(message: Message, pvp_store: PvPStore) -> None:
    if message.from_user is None:
        return
    try:
        removed = await pvp_store.leave_queue(message.from_user.id)
    except PvPBusyError:
        await message.answer("Очередь обновляется. Повторите команду.")
        return
    await message.answer("✅ Вы вышли из очереди." if removed else "Вас не было в очереди.")
