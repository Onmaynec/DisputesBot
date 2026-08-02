from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .config import Settings
from .league_repository import LeagueRepository

router = Router(name="leagues")


@router.message(Command("league"))
async def league_command(
    message: Message,
    league_repository: LeagueRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    player = await league_repository.player(message.from_user.id, settings.pvp_season)
    if player is None:
        await message.answer(
            "Рейтинговая лига появится после первого завершённого PvP-матча. "
            "Начать можно через /duel или /queue."
        )
        return

    form = " · ".join(player.recent_form) if player.recent_form else "нет матчей"
    lines = [
        f"{player.status.icon} Рейтинговая лига — {player.season}",
        "",
        f"Elo: {player.rating} · место: #{player.rank}",
        f"Матчи: {player.games} · {player.wins}/{player.draws}/{player.losses}",
        f"Форма: {form}",
        f"Elo за последние {len(player.recent_form)} матчей: "
        f"{player.recent_rating_delta:+d}",
        "",
    ]
    if player.status.is_placement:
        lines.extend(
            [
                "🧭 Статус: калибровка",
                f"Осталось матчей: {player.status.placement_remaining}",
                "После калибровки дивизион определяется текущим Elo.",
            ]
        )
    else:
        division = player.status.league
        assert division is not None
        lines.append(f"Дивизион: {division.icon} {division.name}")
        lines.append(f"Прогресс: {division.progress_text(player.rating)}")
        if division.next_minimum_rating is None:
            lines.append("Вы достигли максимального дивизиона.")
        else:
            lines.append(
                f"До повышения: {division.rating_to_next(player.rating)} Elo "
                f"(порог {division.next_minimum_rating})"
            )
    lines.extend(["", "Топ: /league_top · распределение: /league_distribution"])
    await message.answer("\n".join(lines))


@router.message(Command("league_top"))
async def league_top_command(
    message: Message,
    league_repository: LeagueRepository,
    settings: Settings,
) -> None:
    entries = await league_repository.top(settings.pvp_season, limit=10)
    if not entries:
        await message.answer("Таблица лиг пока пуста. Завершите первый PvP-матч.")
        return

    lines = [f"🏆 Рейтинговые лиги — {settings.pvp_season}", ""]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for position, entry in enumerate(entries, start=1):
        prefix = medals.get(position, f"{position}.")
        lines.append(
            f"{prefix} {entry.status.icon} {entry.display_name} — "
            f"{entry.rating} Elo · {entry.status.name} · {entry.games} матчей"
        )
    await message.answer("\n".join(lines))


@router.message(Command("league_distribution"))
async def league_distribution_command(
    message: Message,
    league_repository: LeagueRepository,
    settings: Settings,
) -> None:
    distribution = await league_repository.distribution(settings.pvp_season)
    if distribution.total_players == 0:
        await message.answer("В текущем сезоне ещё нет игроков с PvP-рейтингом.")
        return

    lines = [
        f"📊 Распределение лиг — {distribution.season}",
        f"Всего игроков: {distribution.total_players}",
        "",
    ]
    for entry in distribution.entries:
        if entry.players == 0:
            continue
        share = round(entry.players * 100 / distribution.total_players, 1)
        lines.append(f"{entry.icon} {entry.name}: {entry.players} · {share}%")
    lines.extend(
        [
            "",
            "Калибровка требует 5 завершённых матчей.",
            "Дивизионы вычисляются из Elo и не изменяют подбор или награды.",
        ]
    )
    await message.answer("\n".join(lines))
