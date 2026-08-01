from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import Message

from .config import Settings
from .guard import RequestGuard
from .pvp_judge import PvPJudgeEngine, PvPJudgeError
from .pvp_models import PvPMatch, PvPStatus
from .pvp_repository import PvPRecordResult, PvPRepository
from .pvp_store import PvPStore

router = Router(name="pvp-flow")


def _rating_change_text(result: PvPRecordResult, user_id: int) -> str:
    entry = result.entry
    if user_id == entry.pro_user_id:
        before, after = entry.pro_rating_before, entry.pro_rating_after
    else:
        before, after = entry.con_rating_before, entry.con_rating_after
    delta = after - before
    sign = "+" if delta >= 0 else ""
    return f"Elo: {before} → {after} ({sign}{delta})"


async def notify_result(bot: Bot, match: PvPMatch, result: PvPRecordResult) -> None:
    for user_id in (match.pro.user_id, match.con.user_id):
        if match.winner_user_id is None:
            label = "🤝 Ничья"
        elif match.winner_user_id == user_id:
            label = "🏆 Победа"
        else:
            label = "📉 Поражение"
        await bot.send_message(
            user_id,
            "⚖️ Дуэль завершена\n\n"
            f"{label}\n"
            f"Тема: {match.topic}\n"
            f"{_rating_change_text(result, user_id)}\n\n"
            f"Вердикт: {match.verdict_reason}\n\n"
            "Рейтинг: /rating · история: /duel_history",
        )


async def finalize_judging(
    bot: Bot,
    match: PvPMatch,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
    pvp_judge_engine: PvPJudgeEngine,
) -> bool:
    async with pvp_store.hold_match(match.match_id) as acquired:
        if not acquired:
            return False
        current = await pvp_store.get_match(match.match_id)
        if current is None:
            return True
        if current.status is PvPStatus.COMPLETED:
            await pvp_store.finish_match(current)
            return True
        if current.status is not PvPStatus.JUDGING:
            return False
        try:
            judgement = await pvp_judge_engine.judge(current)
        except PvPJudgeError:
            await pvp_store.save_match(current)
            for user_id in (current.pro.user_id, current.con.user_id):
                await bot.send_message(
                    user_id,
                    "⚠️ Судья временно недоступен. Матч сохранён. Отправьте любое "
                    "сообщение или откройте /duel_status, чтобы повторить оценку.",
                )
            return True
        current.complete_judging(judgement.winner_user_id, judgement.reasoning)
        result = await pvp_repository.record_match(current, judgement=judgement)
        await pvp_store.finish_match(current)
        await notify_result(bot, current, result)
        return True


async def process_pvp_argument(
    message: Message,
    *,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
    pvp_judge_engine: PvPJudgeEngine,
    guard: RequestGuard,
    settings: Settings,
) -> bool:
    if message.from_user is None or message.text is None:
        return False
    match = await pvp_store.get_match_for_user(message.from_user.id)
    if match is None:
        return False
    if match.status is PvPStatus.JUDGING:
        await message.answer("⚖️ Повторяю запрос к независимому судье…")
        await finalize_judging(
            message.bot,
            match,
            pvp_store,
            pvp_repository,
            pvp_judge_engine,
        )
        return True
    if len(message.text) > settings.max_argument_chars:
        await message.answer(
            f"Сообщение слишком длинное. Лимит: {settings.max_argument_chars} символов."
        )
        return True
    retry_after = await guard.retry_after(message.from_user.id)
    if retry_after:
        await message.answer(f"⏱ Повторите примерно через {retry_after} сек.")
        return True

    async with guard.hold(message.from_user.id) as acquired:
        if not acquired:
            await message.answer("⏳ Предыдущий ход ещё обрабатывается.")
            return True
        match = await pvp_store.get_match_for_user(message.from_user.id)
        if match is None:
            return True
        try:
            match.add_argument(message.from_user.id, message.text)
        except ValueError as exc:
            await message.answer(f"Ход не принят: {exc}")
            return True
        await pvp_store.save_match(match)

    actor_count = match.argument_count(message.from_user.id)
    if match.status is PvPStatus.JUDGING:
        opponent = match.opponent(message.from_user.id)
        await message.answer(f"✅ Аргумент {actor_count}/3 принят. Передаю матч судье…")
        await message.bot.send_message(
            opponent.user_id,
            f"⚔️ Финальный аргумент оппонента:\n{message.text}\n\nПередаю матч судье…",
        )
        await finalize_judging(
            message.bot,
            match,
            pvp_store,
            pvp_repository,
            pvp_judge_engine,
        )
        return True

    opponent = match.opponent(message.from_user.id)
    await message.answer(
        f"✅ Аргумент {actor_count}/3 принят. Теперь ходит {opponent.display_name}."
    )
    await message.bot.send_message(
        opponent.user_id,
        f"⚔️ Аргумент оппонента:\n{message.text}\n\nВаш ход "
        f"({match.argument_count(opponent.user_id) + 1}/3).",
    )
    return True


@router.message(F.text)
async def pvp_text_handler(
    message: Message,
    pvp_store: PvPStore,
    pvp_repository: PvPRepository,
    pvp_judge_engine: PvPJudgeEngine,
    guard: RequestGuard,
    settings: Settings,
) -> None:
    await process_pvp_argument(
        message,
        pvp_store=pvp_store,
        pvp_repository=pvp_repository,
        pvp_judge_engine=pvp_judge_engine,
        guard=guard,
        settings=settings,
    )
