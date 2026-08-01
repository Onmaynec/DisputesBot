from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)

from .config import Settings
from .pvp_models import PvPMatch, PvPUser
from .pvp_store import PvPBusyError, PvPStore
from .storage import SessionStore

router = Router(name="pvp-invites")


def _identity(user: User) -> PvPUser:
    return PvPUser(
        user_id=user.id,
        username=user.username,
        display_name=user.full_name,
    )


def duel_invitation_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚔️ Принять дуэль",
                    callback_data=f"pvp:accept:{token}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить приглашение",
                    callback_data=f"pvp:cancel-invite:{token}",
                )
            ],
        ]
    )


def _match_started_text(match: PvPMatch, user_id: int) -> str:
    participant = match.participant(user_id)
    opponent = match.opponent(user_id)
    turn = (
        "Ваш ход — сторона «за» начинает первой."
        if match.current_user_id == user_id
        else f"Первым ходит {opponent.display_name}."
    )
    return (
        "⚔️ PvP-дуэль началась\n\n"
        f"Тема: {match.topic}\n"
        f"Ваша позиция: {participant.stance.value}\n"
        f"Оппонент: {opponent.display_name}\n"
        f"Сезон: {match.season}\n\n"
        "У каждого по три аргумента, ходы строго чередуются.\n"
        f"{turn}\n\n"
        "Команды: /duel_status · /forfeit · /cancel_duel"
    )


async def notify_match_started(bot, match: PvPMatch) -> None:
    for user_id in (match.pro.user_id, match.con.user_id):
        await bot.send_message(user_id, _match_started_text(match, user_id))


@router.message(CommandStart())
async def start_v05_command(message: Message) -> None:
    await message.answer(
        "⚔️ Добро пожаловать в DisputesBot v0.5!\n\n"
        "Теперь доступны рейтинговые PvP-дуэли между реальными пользователями.\n\n"
        "/duel [тема] — создать приглашение\n"
        "/queue [тема] — найти соперника\n"
        "/rating — ваш Elo\n"
        "/pvp_leaderboard — рейтинг сезона\n"
        "/duel_history — история дуэлей\n\n"
        "Одиночный спор: /debate [тема]"
    )


@router.message(Command("duel"))
async def duel_command(
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
        await message.answer("Укажите тему: /duel Удалённая работа лучше офисной")
        return
    if len(topic) > settings.max_topic_chars:
        await message.answer(f"Тема длиннее {settings.max_topic_chars} символов.")
        return
    if await store.get_session(message.from_user.id) is not None:
        await message.answer("Сначала завершите одиночный спор командой /cancel.")
        return
    if await pvp_store.get_match_for_user(message.from_user.id) is not None:
        await message.answer("У вас уже есть активная PvP-дуэль: /duel_status")
        return
    invitation = await pvp_store.create_invitation(
        _identity(message.from_user),
        topic=topic,
        season=settings.pvp_season,
    )
    await message.answer(
        "⚔️ Приглашение в PvP-дуэль\n\n"
        f"Автор: {message.from_user.full_name}\n"
        f"Тема: {topic}\n\n"
        "Другой пользователь должен нажать кнопку ниже. Позиции распределятся случайно.",
        reply_markup=duel_invitation_keyboard(invitation.token),
    )


@router.callback_query(F.data.startswith("pvp:accept:"))
async def accept_duel_callback(
    callback: CallbackQuery,
    pvp_store: PvPStore,
    store: SessionStore,
) -> None:
    token = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    invitation = await pvp_store.get_invitation(token)
    if invitation is None:
        await callback.answer("Приглашение устарело", show_alert=True)
        return
    if invitation.inviter.user_id == callback.from_user.id:
        await callback.answer("Нельзя принять собственную дуэль", show_alert=True)
        return
    invitation = await pvp_store.consume_invitation(token)
    if invitation is None:
        await callback.answer("Приглашение уже принято", show_alert=True)
        return
    if await store.get_session(invitation.inviter.user_id) is not None:
        await callback.answer("Автор уже начал другой спор", show_alert=True)
        return
    if await store.get_session(callback.from_user.id) is not None:
        await callback.answer("Сначала завершите свой одиночный спор", show_alert=True)
        return
    try:
        match = await pvp_store.create_match(
            invitation.inviter,
            _identity(callback.from_user),
            topic=invitation.topic,
            season=invitation.season,
        )
    except PvPBusyError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("Дуэль началась")
    if callback.message is not None:
        await callback.message.edit_text(
            f"✅ Дуэль принята пользователем {callback.from_user.full_name}."
        )
    await notify_match_started(callback.bot, match)


@router.callback_query(F.data.startswith("pvp:cancel-invite:"))
async def cancel_duel_invitation_callback(
    callback: CallbackQuery,
    pvp_store: PvPStore,
) -> None:
    token = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    if not await pvp_store.cancel_invitation(token, callback.from_user.id):
        await callback.answer("Отменить может только автор", show_alert=True)
        return
    await callback.answer("Приглашение отменено")
    if callback.message is not None:
        await callback.message.edit_text("🛑 Приглашение в дуэль отменено.")
