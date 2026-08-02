from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .config import Settings
from .league_models import league_for_rating
from .pvp_invites import _identity
from .season_goal_models import (
    GoalDashboard,
    GoalInputError,
    GoalLimitError,
    GoalMetric,
    GoalSuggestion,
    SeasonGoalView,
    format_metric_value,
    league_for_target,
)
from .season_goal_repository import SeasonGoalRepository

router = Router(name="season_goals")


def _progress_bar(progress: float) -> str:
    filled = max(0, min(10, round(progress * 10)))
    return "█" * filled + "░" * (10 - filled)


def _current_value(goal: SeasonGoalView) -> str:
    if goal.metric is GoalMetric.LEAGUE:
        league = league_for_rating(round(goal.current_value))
        return f"{league.icon} {league.name} · {round(goal.current_value)} Elo"
    return format_metric_value(goal.metric, goal.current_value)


def _target_argument(suggestion: GoalSuggestion) -> str:
    if suggestion.metric is GoalMetric.LEAGUE:
        return league_for_target(suggestion.target_value).league_id.value
    value = suggestion.target_value
    return str(round(value)) if value.is_integer() else f"{value:.1f}"


def render_goal_dashboard(dashboard: GoalDashboard) -> str:
    if not dashboard.goals:
        return (
            "🎯 Сезонные цели\n"
            f"Сезон: {dashboard.season}\n\n"
            "Целей пока нет.\n"
            "Создать: /set_goal elo 1200\n"
            "Подсказки: /goal_suggest"
        )

    lines = [
        "🎯 Сезонные цели",
        f"Сезон: {dashboard.season}",
        f"Активные: {dashboard.active_count} · завершённые: {dashboard.completed_count}",
        "",
    ]
    for goal in dashboard.goals:
        definition = goal.definition
        marker = "✅" if goal.is_completed else "🎯"
        lines.append(f"{marker} {definition.icon} {definition.label}")
        lines.append(
            f"{_current_value(goal)} → {format_metric_value(goal.metric, goal.target_value)}"
        )
        lines.append(f"{_progress_bar(goal.progress)} {goal.progress_percent}%")
        if not goal.sample_requirement_met:
            lines.append(
                f"Проверка откроется после {definition.minimum_samples} образцов "
                f"(сейчас {goal.samples})."
            )
        elif goal.is_completed:
            lines.append("Цель зафиксирована как выполненная.")
        lines.append("")
    lines.extend(
        [
            "Изменить: /set_goal МЕТРИКА ЦЕЛЬ",
            "Удалить: /delete_goal МЕТРИКА",
            "Подсказки: /goal_suggest",
        ]
    )
    return "\n".join(lines)


@router.message(Command("goals"))
async def goals_command(
    message: Message,
    season_goal_repository: SeasonGoalRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    dashboard = await season_goal_repository.dashboard(
        message.from_user.id,
        settings.pvp_season,
    )
    await message.answer(render_goal_dashboard(dashboard))


@router.message(Command("set_goal"))
async def set_goal_command(
    message: Message,
    command: CommandObject,
    season_goal_repository: SeasonGoalRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(
            "Формат: /set_goal МЕТРИКА ЦЕЛЬ\n"
            "Примеры:\n"
            "/set_goal elo 1200\n"
            "/set_goal league diamond\n"
            "/set_goal wins 20\n"
            "/set_goal logic 8.0\n\n"
            "Метрики: elo, league, wins, matches, win_rate, streak, "
            "logic, evidence, rebuttal."
        )
        return
    try:
        result = await season_goal_repository.set_goal(
            _identity(message.from_user),
            settings.pvp_season,
            parts[0],
            parts[1],
        )
    except (GoalInputError, GoalLimitError) as exc:
        await message.answer(f"⚠️ {exc}")
        return

    action = "создана" if result.created else "обновлена"
    goal = result.goal
    await message.answer(
        f"✅ Цель {action}.\n"
        f"{goal.definition.icon} {goal.definition.label}: "
        f"{_current_value(goal)} → {format_metric_value(goal.metric, goal.target_value)}\n"
        "Прогресс: /goals"
    )


@router.message(Command("delete_goal"))
async def delete_goal_command(
    message: Message,
    command: CommandObject,
    season_goal_repository: SeasonGoalRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    metric = (command.args or "").strip()
    if not metric:
        await message.answer("Формат: /delete_goal МЕТРИКА")
        return
    try:
        deleted = await season_goal_repository.delete_goal(
            message.from_user.id,
            settings.pvp_season,
            metric,
        )
    except GoalInputError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    if not deleted:
        await message.answer("Цель с такой метрикой не найдена.")
        return
    await message.answer("🗑 Цель удалена.")


@router.message(Command("goal_suggest"))
async def goal_suggest_command(
    message: Message,
    season_goal_repository: SeasonGoalRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    suggestions = await season_goal_repository.suggestions(
        message.from_user.id,
        settings.pvp_season,
    )
    if not suggestions:
        await message.answer(
            "Новых рекомендаций нет: активные цели уже покрывают основные направления."
        )
        return
    lines = ["🧭 Рекомендуемые цели", f"Сезон: {settings.pvp_season}", ""]
    for suggestion in suggestions:
        lines.append(
            f"• {format_metric_value(suggestion.metric, suggestion.target_value)} — "
            f"{suggestion.reason}"
        )
        lines.append(
            f"  /set_goal {suggestion.metric.value} {_target_argument(suggestion)}"
        )
    lines.extend(
        [
            "",
            "Рекомендации детерминированы и не вызывают OpenAI.",
        ]
    )
    await message.answer("\n".join(lines))
