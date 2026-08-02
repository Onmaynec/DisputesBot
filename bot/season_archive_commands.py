from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .season_archive_repository import SeasonArchiveRepository

router = Router(name="season_archive")


@router.message(Command("pvp_career"))
async def pvp_career_command(
    message: Message,
    season_archive_repository: SeasonArchiveRepository,
) -> None:
    if message.from_user is None:
        return
    career = await season_archive_repository.career(message.from_user.id)
    if career is None:
        await message.answer(
            "Карьерная статистика появится после первого завершённого PvP-матча."
        )
        return

    best = career.best_season
    lines = [
        f"🗂 PvP-карьера — {career.display_name}",
        "",
        f"Сезонов: {len(career.seasons)} · матчей: {career.total_games}",
        f"Рекорд: {career.total_wins}/{career.total_draws}/{career.total_losses}",
        f"Победы: {career.win_rate:.1f}% · карьерный пик: {career.peak_rating} Elo",
        f"Лучший сезон: {best.season} · {best.rating} Elo · место #{best.rank}",
        "",
        "Сезоны:",
    ]
    for item in career.seasons[:10]:
        delta = f"{item.net_rating:+d}"
        lines.append(
            f"{item.status.icon} {item.season}: {item.rating} Elo "
            f"(пик {item.peak_rating}, {delta}) · #{item.rank} · "
            f"{item.wins}/{item.draws}/{item.losses}"
        )
    lines.extend(
        [
            "",
            "Архив таблицы: /season_archive <сезон>",
            "Чемпионы: /hall_of_fame",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("season_archive"))
async def season_archive_command(
    message: Message,
    command: CommandObject,
    season_archive_repository: SeasonArchiveRepository,
    settings: Settings,
) -> None:
    season = (command.args or "").strip()
    if not season:
        entries = await season_archive_repository.catalog(limit=12)
        if not entries:
            await message.answer("Сезонный архив пока пуст.")
            return
        lines = ["🗃 Доступные PvP-сезоны", ""]
        for entry in entries:
            current = " · текущий" if entry.season == settings.pvp_season else ""
            lines.append(
                f"{entry.champion_status.icon} {entry.season}{current}: "
                f"{entry.players} игроков · {entry.matches} матчей"
            )
        lines.extend(["", "Открыть таблицу: /season_archive <сезон>"])
        await message.answer("\n".join(lines))
        return

    archive = await season_archive_repository.archive(season, limit=10)
    if archive is None:
        await message.answer(
            "Сезон не найден. Используйте /season_archive без аргумента для списка."
        )
        return

    lines = [
        f"🏆 Архив сезона — {archive.season}",
        f"Игроков: {archive.total_players} · матчей: {archive.total_matches}",
        "",
    ]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for entry in archive.standings:
        prefix = medals.get(entry.rank, f"{entry.rank}.")
        lines.append(
            f"{prefix} {entry.status.icon} {entry.display_name} — "
            f"{entry.rating} Elo · {entry.wins}/{entry.draws}/{entry.losses}"
        )
    lines.extend(
        [
            "",
            "Рейтинг отображает сохранённый итог сезона или текущее значение, "
            "если сезон ещё активен.",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("hall_of_fame"))
async def hall_of_fame_command(
    message: Message,
    season_archive_repository: SeasonArchiveRepository,
    settings: Settings,
) -> None:
    entries = await season_archive_repository.catalog(limit=20)
    if not entries:
        await message.answer("Зал славы пока пуст.")
        return

    lines = ["👑 PvP Hall of Fame", ""]
    for entry in entries:
        current = " · лидер сейчас" if entry.season == settings.pvp_season else ""
        lines.append(
            f"{entry.champion_status.icon} {entry.season}: {entry.champion_name} — "
            f"{entry.champion_rating} Elo · {entry.champion_games} матчей{current}"
        )
    lines.extend(
        [
            "",
            "Чемпион определяется теми же стабильными правилами, что и лидерборд: "
            "Elo, матчи, время обновления и user ID.",
        ]
    )
    await message.answer("\n".join(lines))
