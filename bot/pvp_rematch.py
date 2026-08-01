from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .moderation_repository import ModerationRepository
from .pvp_invites import _identity, duel_invitation_keyboard
from .pvp_repository import PvPRepository
from .pvp_store import PvPBusyError, PvPStore
from .storage import SessionStore

router = Router(name="v06-rematch")


@router.message(Command("rematch_duel"))
async def rematch_duel_command(
    message: Message,
    command: CommandObject,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
    moderation_repository: ModerationRepository,
    store: SessionStore,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    user_id = message.from_user.id
    if await store.get_session(user_id) is not None:
        await message.answer("Сначала завершите одиночный спор командой /cancel.")
        return
    if await pvp_store.get_match_for_user(user_id) is not None:
        await message.answer("У вас уже есть активная PvP-дуэль: /duel_status")
        return
    history = await pvp_repository.history(user_id, limit=1)
    if not history:
        await message.answer("В истории ещё нет соперника для рематча.")
        return
    previous = history[0]
    opponent_id = (
        previous.con_user_id if previous.pro_user_id == user_id else previous.pro_user_id
    )
    if not await moderation_repository.pair_allowed(user_id, opponent_id):
        await message.answer("Рематч недоступен из-за блокировки между участниками.")
        return
    opponent = await pvp_repository.user_identity(opponent_id)
    if opponent is None:
        await message.answer("Профиль прошлого соперника больше недоступен.")
        return
    topic = (command.args or previous.topic).strip()
    if not topic:
        topic = previous.topic
    if len(topic) > settings.max_topic_chars:
        await message.answer(f"Тема длиннее {settings.max_topic_chars} символов.")
        return
    rated_hint = await pvp_repository.can_rate_pair(
        user_id,
        opponent_id,
        settings.pvp_season,
    )
    try:
        invitation = await pvp_store.create_invitation(
            _identity(message.from_user),
            topic=topic,
            season=settings.pvp_season,
            target_user_id=opponent_id,
            source_match_id=previous.match_id,
            rated_hint=rated_hint,
        )
    except PvPBusyError as exc:
        await message.answer(str(exc))
        return
    rating_text = (
        "Матч будет рейтинговым."
        if rated_hint
        else "Лимит пары исчерпан: матч сохранится, но Elo не изменится."
    )
    text = (
        "🔁 Персональное приглашение на рематч\n\n"
        f"Соперник: {opponent.display_name}\n"
        f"Тема: {topic}\n"
        f"{rating_text}\n\n"
        "Принять может только указанный соперник."
    )
    await message.answer(text, reply_markup=duel_invitation_keyboard(invitation.token))
    try:
        await message.bot.send_message(
            opponent_id,
            text,
            reply_markup=duel_invitation_keyboard(invitation.token),
        )
    except Exception:
        await message.answer(
            "Приглашение создано, но сопернику не удалось отправить уведомление. "
            "Перешлите ему сообщение с кнопкой."
        )
