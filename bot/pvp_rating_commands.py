from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .config import Settings
from .pvp_repository import PvPRepository

router = Router(name="pvp-rating")


@router.message(Command("rating"))
async def rating_command(
    message: Message,
    pvp_repository: PvPRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    rating = await pvp_repository.rating(message.from_user.id, settings.pvp_season)
    if rating is None:
        await message.answer("Рейтинговых дуэлей пока нет. Начните с /duel или /queue.")
        return
    rank = await pvp_repository.rank(message.from_user.id, settings.pvp_season)
    await message.answer(
        "🏅 PvP-рейтинг\n\n"
        f"Сезон: {rating.season}\n"
        f"Elo: {rating.rating}\n"
        f"Место: {rank or '—'}\n"
        f"Игры: {rating.games}\n"
        f"Победы / ничьи / поражения: {rating.wins} / {rating.draws} / {rating.losses}"
    )


@router.message(Command("pvp_leaderboard"))
async def pvp_leaderboard_command(
    message: Message,
    pvp_repository: PvPRepository,
    settings: Settings,
) -> None:
    entries = await pvp_repository.top(settings.pvp_season, 10)
    if not entries:
        await message.answer("PvP-рейтинг сезона пока пуст.")
        return
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"🏆 PvP-лидерборд · {settings.pvp_season}", ""]
    for position, entry in enumerate(entries, start=1):
        label = f"@{entry.username}" if entry.username else entry.display_name
        lines.append(
            f"{medals.get(position, f'{position}.')} {label} — {entry.rating} Elo, "
            f"игр: {entry.games}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("duel_history"))
async def duel_history_command(
    message: Message,
    pvp_repository: PvPRepository,
) -> None:
    if message.from_user is None:
        return
    entries = await pvp_repository.history(message.from_user.id, 5)
    if not entries:
        await message.answer("История PvP-дуэлей пока пуста.")
        return
    lines = ["📚 Последние PvP-дуэли", ""]
    for index, entry in enumerate(entries, start=1):
        if entry.winner_user_id is None:
            result = "ничья"
        elif entry.winner_user_id == message.from_user.id:
            result = "победа"
        else:
            result = "поражение"
        if message.from_user.id == entry.pro_user_id:
            delta = entry.pro_rating_after - entry.pro_rating_before
        else:
            delta = entry.con_rating_after - entry.con_rating_before
        sign = "+" if delta >= 0 else ""
        lines.append(
            f"{index}. {entry.ended_at:%d.%m.%Y} · {result} · {sign}{delta} Elo\n"
            f"{entry.topic}"
        )
    await message.answer("\n\n".join(lines))
