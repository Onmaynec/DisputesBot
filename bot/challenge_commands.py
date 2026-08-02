from __future__ import annotations

from math import ceil

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, User

from .challenge_models import ChallengeError, ChallengeView
from .challenge_repository import ChallengeRepository
from .config import Settings
from .pvp_invites import notify_match_started
from .pvp_models import PvPUser
from .pvp_store import PvPBusyError, PvPStore
from .storage import SessionStore

router = Router(name="challenges")


def _identity(user: User) -> PvPUser:
    return PvPUser(
        user_id=user.id,
        username=user.username,
        display_name=user.full_name,
    )


def _hours_remaining(challenge: ChallengeView) -> int:
    seconds = (challenge.expires_at - challenge.created_at).total_seconds()
    return max(0, ceil(seconds / 3600))


async def _send_safely(bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    return True


def _challenge_line(challenge: ChallengeView, *, incoming: bool) -> str:
    player = challenge.challenger if incoming else challenge.target
    direction = "от" if incoming else "для"
    return (
        f"• {challenge.challenge_id} {direction} {player.display_name}\n"
        f"  Тема: {challenge.topic}\n"
        f"  Действует до: {challenge.expires_at:%Y-%m-%d %H:%M} UTC"
    )


@router.message(Command("challenge"))
async def challenge_command(
    message: Message,
    command: CommandObject,
    challenge_repository: ChallengeRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    raw = (command.args or "").strip()
    target: PvPUser | None = None
    topic = ""

    reply_user = (
        message.reply_to_message.from_user
        if message.reply_to_message is not None
        else None
    )
    if reply_user is not None and not reply_user.is_bot:
        target = _identity(reply_user)
        topic = raw
    else:
        parts = raw.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            target = await challenge_repository.resolve_user(int(parts[0]))
            topic = parts[1].strip()

    if target is None:
        await message.answer(
            "Ответьте на сообщение соперника: /challenge тема\n"
            "или используйте: /challenge user_id тема"
        )
        return
    if not topic:
        await message.answer("Укажите тему персонального вызова.")
        return
    if len(topic) > settings.max_topic_chars:
        await message.answer(f"Тема длиннее {settings.max_topic_chars} символов.")
        return

    try:
        created, challenge = await challenge_repository.create(
            _identity(message.from_user),
            target,
            season=settings.pvp_season,
            topic=topic,
        )
    except ChallengeError as exc:
        await message.answer(str(exc))
        return

    if not created:
        await message.answer(
            "У этой пары уже есть активный вызов.\n"
            f"ID: {challenge.challenge_id} · список: /challenges"
        )
        return

    hours = _hours_remaining(challenge)
    delivered = await _send_safely(
        message.bot,
        challenge.target.user_id,
        "⚔️ Вам отправлен персональный PvP-вызов\n\n"
        f"От: {challenge.challenger.display_name}\n"
        f"Тема: {challenge.topic}\n"
        f"Сезон: {challenge.season}\n"
        f"Срок: {hours} ч.\n\n"
        f"Принять: /accept_challenge {challenge.challenge_id}\n"
        f"Отклонить: /decline_challenge {challenge.challenge_id}\n"
        "Все вызовы: /challenges",
    )
    delivery_text = (
        "Соперник уведомлён."
        if delivered
        else "Личное уведомление недоступно; вызов сохранён в /challenges."
    )
    await message.answer(
        "✅ Персональный вызов создан\n\n"
        f"ID: {challenge.challenge_id}\n"
        f"Соперник: {challenge.target.display_name}\n"
        f"Тема: {challenge.topic}\n"
        f"Срок: {hours} ч.\n"
        f"{delivery_text}\n\n"
        f"Отменить: /cancel_challenge {challenge.challenge_id}"
    )


@router.message(Command("challenges"))
async def challenges_command(
    message: Message,
    challenge_repository: ChallengeRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    inbox = await challenge_repository.inbox(message.from_user.id, settings.pvp_season)
    if not inbox.incoming and not inbox.outgoing:
        await message.answer(
            "Активных персональных вызовов нет.\n"
            "Создать: ответьте на сообщение командой /challenge тема."
        )
        return
    lines = [f"⚔️ Персональные вызовы — {settings.pvp_season}", ""]
    if inbox.incoming:
        lines.append("Входящие:")
        lines.extend(_challenge_line(item, incoming=True) for item in inbox.incoming)
        lines.extend(
            [
                "",
                "Принять: /accept_challenge ID",
                "Отклонить: /decline_challenge ID",
                "",
            ]
        )
    if inbox.outgoing:
        lines.append("Исходящие:")
        lines.extend(_challenge_line(item, incoming=False) for item in inbox.outgoing)
        lines.extend(["", "Отменить: /cancel_challenge ID"])
    await message.answer("\n".join(lines))


@router.message(Command("accept_challenge"))
async def accept_challenge_command(
    message: Message,
    command: CommandObject,
    challenge_repository: ChallengeRepository,
    pvp_store: PvPStore,
    store: SessionStore,
) -> None:
    if message.from_user is None:
        return
    challenge_id = (command.args or "").strip().lower()
    if not challenge_id:
        await message.answer("Укажите ID: /accept_challenge ID")
        return
    if await store.get_session(message.from_user.id) is not None:
        await message.answer("Сначала завершите одиночный спор командой /cancel.")
        return

    try:
        challenge = await challenge_repository.claim_accept(
            challenge_id,
            message.from_user.id,
        )
    except ChallengeError as exc:
        await message.answer(str(exc))
        return

    if await store.get_session(challenge.challenger.user_id) is not None:
        await challenge_repository.release_accept(challenge.challenge_id)
        await message.answer("Автор вызова сейчас участвует в одиночном споре.")
        return

    challenger = PvPUser(
        user_id=challenge.challenger.user_id,
        username=challenge.challenger.username,
        display_name=challenge.challenger.display_name,
    )
    try:
        match = await pvp_store.create_match(
            challenger,
            _identity(message.from_user),
            topic=challenge.topic,
            season=challenge.season,
        )
    except PvPBusyError as exc:
        await challenge_repository.release_accept(challenge.challenge_id)
        await message.answer(str(exc))
        return

    try:
        await challenge_repository.complete_accept(challenge.challenge_id, match.match_id)
    except ChallengeError:
        await pvp_store.cancel_match(match)
        await challenge_repository.release_accept(challenge.challenge_id)
        await message.answer("Не удалось подтвердить вызов. Попробуйте ещё раз.")
        return

    await message.answer("✅ Вызов принят. PvP-матч запущен.")
    try:
        await notify_match_started(message.bot, match)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


@router.message(Command("decline_challenge"))
async def decline_challenge_command(
    message: Message,
    command: CommandObject,
    challenge_repository: ChallengeRepository,
) -> None:
    if message.from_user is None:
        return
    challenge_id = (command.args or "").strip().lower()
    if not challenge_id:
        await message.answer("Укажите ID: /decline_challenge ID")
        return
    try:
        challenge = await challenge_repository.decline(challenge_id, message.from_user.id)
    except ChallengeError as exc:
        await message.answer(str(exc))
        return
    await _send_safely(
        message.bot,
        challenge.challenger.user_id,
        f"Вызов {challenge.challenge_id} отклонён игроком "
        f"{challenge.target.display_name}.",
    )
    await message.answer("Вызов отклонён.")


@router.message(Command("cancel_challenge"))
async def cancel_challenge_command(
    message: Message,
    command: CommandObject,
    challenge_repository: ChallengeRepository,
) -> None:
    if message.from_user is None:
        return
    challenge_id = (command.args or "").strip().lower()
    if not challenge_id:
        await message.answer("Укажите ID: /cancel_challenge ID")
        return
    try:
        challenge = await challenge_repository.cancel(challenge_id, message.from_user.id)
    except ChallengeError as exc:
        await message.answer(str(exc))
        return
    await _send_safely(
        message.bot,
        challenge.target.user_id,
        f"Вызов {challenge.challenge_id} отменён автором "
        f"{challenge.challenger.display_name}.",
    )
    await message.answer("Вызов отменён.")
