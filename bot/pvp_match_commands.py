from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .pvp_flow import finalize_judging, notify_result
from .pvp_judge import PvPJudgeEngine
from .pvp_models import PvPStatus
from .pvp_repository import PvPRepository
from .pvp_store import PvPStore

router = Router(name="pvp-match-commands")


@router.message(Command("duel_status"))
async def duel_status_command(
    message: Message,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
    pvp_judge_engine: PvPJudgeEngine,
) -> None:
    if message.from_user is None:
        return
    match = await pvp_store.get_match_for_user(message.from_user.id)
    if match is None:
        await message.answer("Активной PvP-дуэли нет. Используйте /duel или /queue.")
        return
    if match.status is PvPStatus.JUDGING:
        await message.answer("⚖️ Матч завершён по ходам. Повторяю судейство…")
        await finalize_judging(
            message.bot,
            match,
            pvp_store,
            pvp_repository,
            pvp_judge_engine,
        )
        return
    current = match.participant(match.current_user_id) if match.current_user_id else None
    opponent = match.opponent(message.from_user.id)
    await message.answer(
        "⚔️ Состояние дуэли\n\n"
        f"Тема: {match.topic}\n"
        f"Позиция: {match.participant(message.from_user.id).stance.value}\n"
        f"Ваши аргументы: {match.argument_count(message.from_user.id)}/3\n"
        f"Аргументы оппонента: {match.argument_count(opponent.user_id)}/3\n"
        f"Сейчас ходит: {current.display_name if current else 'судья'}"
    )


@router.message(Command("cancel_duel"))
async def cancel_duel_command(message: Message, pvp_store: PvPStore) -> None:
    if message.from_user is None:
        return
    match = await pvp_store.get_match_for_user(message.from_user.id)
    if match is None:
        await message.answer("Активной дуэли нет.")
        return
    try:
        await pvp_store.cancel_match(match)
    except ValueError:
        await message.answer("После первого аргумента можно только сдаться: /forfeit")
        return
    for user_id in (match.pro.user_id, match.con.user_id):
        await message.bot.send_message(user_id, "🛑 Дуэль отменена до первого хода. Elo не изменён.")


@router.message(Command("forfeit"))
async def forfeit_command(
    message: Message,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
) -> None:
    if message.from_user is None:
        return
    match = await pvp_store.get_match_for_user(message.from_user.id)
    if match is None:
        await message.answer("Активной дуэли нет.")
        return
    if not match.arguments:
        await message.answer("Матч ещё не начался. Используйте /cancel_duel без потери Elo.")
        return
    async with pvp_store.hold_match(match.match_id) as acquired:
        if not acquired:
            await message.answer("Матч уже завершается. Повторите позже.")
            return
        match = await pvp_store.get_match(match.match_id)
        if match is None:
            return
        match.forfeit(message.from_user.id)
        result = await pvp_repository.record_match(match)
        await pvp_store.finish_match(match)
    await notify_result(message.bot, match, result)
