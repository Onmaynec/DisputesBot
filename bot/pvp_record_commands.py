from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .pvp_record_repository import PvPRecordRepository

router = Router(name="pvp_records")


def _format_integer(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


@router.message(Command("pvp_records"))
async def pvp_records_command(
    message: Message,
    pvp_record_repository: PvPRecordRepository,
) -> None:
    if message.from_user is None:
        return
    book = await pvp_record_repository.personal(message.from_user.id)
    if book is None:
        await message.answer("Книга рекордов появится после первого завершённого PvP-матча.")
        return

    lines = [
        f"📚 PvP Record Book — {book.display_name}",
        "",
        f"Сезонов: {book.seasons} · матчей: {book.total_matches}",
        f"Рекорд: {book.wins}/{book.draws}/{book.losses} · победы {book.win_rate:.1f}%",
        f"Уникальных соперников: {book.distinct_opponents}",
        "",
    ]
    if book.longest_win_streak is None:
        lines.append("🔥 Серия побед: —")
    else:
        lines.append(
            f"🔥 Серия побед: {book.longest_win_streak.wins} · "
            f"{book.longest_win_streak.season}"
        )

    if book.best_rating_gain is None:
        lines.append("📈 Лучший Elo-прирост: —")
    else:
        lines.append(
            f"📈 Лучший Elo-прирост: +{_format_integer(book.best_rating_gain.value)} "
            f"против {book.best_rating_gain.opponent_name} · "
            f"{book.best_rating_gain.season}"
        )

    if book.biggest_upset is None:
        lines.append("⚡ Крупнейший апсет: —")
    else:
        lines.append(
            f"⚡ Крупнейший апсет: {int(book.biggest_upset.value)} Elo "
            f"против {book.biggest_upset.opponent_name} · {book.biggest_upset.season}"
        )

    if book.highest_score is None:
        lines.append("🧠 Лучший судейский счёт: —")
    else:
        lines.append(
            f"🧠 Лучший судейский счёт: {book.highest_score.value:.1f}/30 "
            f"против {book.highest_score.opponent_name} · {book.highest_score.season}"
        )

    if book.favorite_rival is None:
        lines.append("🤝 Главный соперник: —")
    else:
        lines.append(
            f"🤝 Главный соперник: {book.favorite_rival.opponent_name} · "
            f"{book.favorite_rival.matches} матчей"
        )

    lines.extend(
        [
            "",
            "Сезонные рекорды: /season_records",
            "Итоги и сравнение сезонов: /season_recap · /compare_seasons",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("season_records"))
async def season_records_command(
    message: Message,
    command: CommandObject,
    pvp_record_repository: PvPRecordRepository,
    settings: Settings,
) -> None:
    season = (command.args or settings.pvp_season).strip()
    book = await pvp_record_repository.season(season)
    if book is None:
        await message.answer(
            "Сезон не найден. Список доступных сезонов: /season_archive"
        )
        return

    lines = [
        f"🏅 Рекорды сезона — {book.season}",
        f"Игроков: {book.total_players} · матчей: {book.total_matches}",
        "",
    ]
    if book.most_wins is not None:
        lines.append(
            f"🏆 Больше побед: {book.most_wins.display_name} — {book.most_wins.value}"
        )
    if book.most_games is not None:
        lines.append(
            f"⚔️ Больше матчей: {book.most_games.display_name} — {book.most_games.value}"
        )
    if book.longest_win_streak is not None:
        lines.append(
            "🔥 Длиннейшая серия: "
            f"{book.longest_win_streak.display_name} — "
            f"{book.longest_win_streak.value} побед"
        )
    if book.biggest_upset is not None:
        lines.append(
            f"⚡ Главный апсет: {book.biggest_upset.winner_name} победил "
            f"{book.biggest_upset.loser_name} · разница {book.biggest_upset.elo_gap} Elo"
        )
    if book.busiest_rivalry is not None:
        lines.append(
            f"🤝 Главное противостояние: {book.busiest_rivalry.first_name} — "
            f"{book.busiest_rivalry.second_name} · {book.busiest_rivalry.matches} матчей"
        )

    lines.extend(
        [
            "",
            "Публичная доска использует только результаты, Elo и число матчей. "
            "Темы, аргументы и приватные судейские оценки не показываются.",
        ]
    )
    await message.answer("\n".join(lines))
