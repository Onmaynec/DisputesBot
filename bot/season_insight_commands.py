from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .season_insight_models import SeasonComparison, SeasonRecap
from .season_insight_repository import SeasonInsightRepository

router = Router(name="season_insights")


def _division_text(recap: SeasonRecap) -> str:
    if recap.status.is_placement:
        return f"🧭 Калибровка · осталось {recap.status.placement_remaining}"
    division = recap.status.league
    assert division is not None
    return f"{division.icon} {division.name}"


def _signed(value: int | float, *, digits: int = 0) -> str:
    return f"{value:+.{digits}f}" if digits else f"{int(value):+d}"


def _format_comparison(comparison: SeasonComparison) -> str:
    older = comparison.older
    newer = comparison.newer
    lines = [
        "⚖️ Сравнение PvP-сезонов",
        f"{older.season} → {newer.season}",
        "",
        f"Elo: {older.rating} → {newer.rating} ({_signed(comparison.rating_delta)})",
        f"Пиковый Elo: {older.peak_rating} → {newer.peak_rating} "
        f"({_signed(comparison.peak_delta)})",
        f"Win rate: {older.win_rate:.1f}% → {newer.win_rate:.1f}% "
        f"({_signed(comparison.win_rate_delta, digits=1)} п.п.)",
        f"Матчи: {older.games} → {newer.games} ({_signed(comparison.games_delta)})",
        f"Лучшая серия: {older.longest_win_streak} → {newer.longest_win_streak} "
        f"({_signed(comparison.streak_delta)})",
    ]
    skill_delta = comparison.skill_total_delta
    if skill_delta is not None:
        assert older.skills is not None and newer.skills is not None
        lines.append(
            f"Средний судейский балл: {older.skills.total:.1f} → "
            f"{newer.skills.total:.1f} ({_signed(skill_delta, digits=1)})"
        )
    if comparison.rating_delta > 0:
        conclusion = "📈 Финальный Elo вырос."
    elif comparison.rating_delta < 0:
        conclusion = "📉 Финальный Elo снизился; используйте /pvp_coach для разбора."
    else:
        conclusion = "➖ Финальный Elo не изменился."
    lines.extend(["", conclusion])
    return "\n".join(lines)


@router.message(Command("season_recap"))
async def season_recap_command(
    message: Message,
    command: CommandObject,
    season_insight_repository: SeasonInsightRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    season = (command.args or settings.pvp_season).strip()
    recap = await season_insight_repository.recap(message.from_user.id, season)
    if recap is None:
        await message.answer(
            "Сезон не найден в вашей PvP-карьере. Используйте /pvp_career, "
            "чтобы увидеть доступные season ID."
        )
        return

    lines = [
        f"📊 Итоги PvP-сезона — {recap.season}",
        _division_text(recap),
        "",
        f"Elo: {recap.starting_rating} → {recap.rating} "
        f"({_signed(recap.net_rating)}) · пик {recap.peak_rating}",
        f"Место: #{recap.rank} из {recap.total_players}",
        f"Матчи: {recap.games} · {recap.wins}/{recap.draws}/{recap.losses}",
        f"Win rate: {recap.win_rate:.1f}%",
        f"Рейтинговые: {recap.rated_matches} · нерейтинговые: {recap.unrated_matches}",
        f"Уникальные соперники: {recap.unique_opponents}",
        f"Лучшая серия побед: {recap.longest_win_streak}",
    ]
    if recap.favorite_opponent_id is not None:
        lines.append(
            f"Главный соперник: {recap.favorite_opponent_name} · "
            f"{recap.favorite_opponent_matches} матчей"
        )
    if recap.skills is not None:
        lines.extend(
            [
                "",
                f"🧠 Средние навыки за {recap.skills.scored_matches} матчей:",
                f"Логика {recap.skills.logic:.1f} · "
                f"доказательства {recap.skills.evidence:.1f} · "
                f"опровержение {recap.skills.rebuttal:.1f}",
                f"Сильная сторона: {recap.skills.strongest_label}",
                f"Фокус тренировки: {recap.skills.focus_label}",
            ]
        )
    lines.extend(
        [
            "",
            f"🎁 Ranked rewards: {recap.claimed_milestones} milestones · "
            f"{recap.claimed_tokens} 🪙",
            "Сравнение: /compare_seasons · рекорды: /career_records",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("compare_seasons"))
async def compare_seasons_command(
    message: Message,
    command: CommandObject,
    season_insight_repository: SeasonInsightRepository,
) -> None:
    if message.from_user is None:
        return
    arguments = (command.args or "").split()
    if not arguments:
        comparison = await season_insight_repository.compare_recent(message.from_user.id)
    elif len(arguments) == 2:
        comparison = await season_insight_repository.compare(
            message.from_user.id,
            arguments[0],
            arguments[1],
        )
    else:
        await message.answer(
            "Использование: /compare_seasons SEASON_1 SEASON_2. "
            "Без аргументов сравниваются два последних сезона."
        )
        return
    if comparison is None:
        await message.answer(
            "Для сравнения нужны два разных сезона из вашей PvP-карьеры. "
            "Список доступен в /pvp_career."
        )
        return
    await message.answer(_format_comparison(comparison))


@router.message(Command("career_records"))
async def career_records_command(
    message: Message,
    season_insight_repository: SeasonInsightRepository,
) -> None:
    if message.from_user is None:
        return
    records = await season_insight_repository.records(message.from_user.id)
    if records is None:
        await message.answer("Карьерные рекорды появятся после первого PvP-матча.")
        return

    lines = [
        "🏅 Личные PvP-рекорды",
        f"Сезонов в карьере: {records.seasons_count}",
        "",
        f"Высший итоговый Elo: {records.highest_final.rating} "
        f"({records.highest_final.season})",
        f"Абсолютный пик Elo: {records.highest_peak.peak_rating} "
        f"({records.highest_peak.season})",
        f"Больше всего побед: {records.most_wins.wins} ({records.most_wins.season})",
        f"Больше всего матчей: {records.most_games.games} ({records.most_games.season})",
        f"Лучший win rate: {records.best_win_rate.win_rate:.1f}% "
        f"({records.best_win_rate.season})",
        f"Лучший прирост Elo: {_signed(records.biggest_gain.net_rating)} "
        f"({records.biggest_gain.season})",
        f"Лучшая серия побед: {records.longest_streak.longest_win_streak} "
        f"({records.longest_streak.season})",
        "",
        "Подробный сезон: /season_recap SEASON_ID",
    ]
    await message.answer("\n".join(lines))
