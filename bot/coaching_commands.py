from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .coaching_models import CoachingSkill, MatchReview
from .coaching_repository import CoachingRepository
from .config import Settings

router = Router(name="coaching")


def _score(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _skill_line(review: MatchReview, skill: CoachingSkill) -> str:
    own = review.own_scores.value(skill)
    opponent = review.opponent_scores.value(skill)
    gap = own - opponent
    return (
        f"{skill.icon} {skill.label}: {_score(own)}/10 · "
        f"соперник {_score(opponent)}/10 · {gap:+.1f}"
    )


def _trend_text(delta: float | None) -> str:
    if delta is None:
        return "нужно минимум четыре оценённых матча"
    if delta > 0.5:
        return f"📈 рост на {delta:+.1f} балла"
    if delta < -0.5:
        return f"📉 снижение на {delta:+.1f} балла"
    return f"➡️ стабильно ({delta:+.1f})"


@router.message(Command("match_review"))
async def match_review_command(
    message: Message,
    command: CommandObject,
    coaching_repository: CoachingRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    match_id = (command.args or "").strip() or None
    review = await coaching_repository.match_review(
        message.from_user.id,
        settings.pvp_season,
        match_id,
    )
    if review is None:
        suffix = " с таким ID" if match_id is not None else ""
        await message.answer(
            "Не найден оценённый PvP-матч"
            f"{suffix} в текущем сезоне. Разбор доступен после полного матча, "
            "завершённого независимым судьёй."
        )
        return

    rating = (
        f"{review.rating_delta:+d} Elo"
        if review.rated
        else "нерейтинговый матч · Elo не изменён"
    )
    strongest = review.own_scores.strongest_skill
    focus = review.own_scores.focus_skill
    lines = [
        f"🧩 Разбор PvP-матча · {review.match_id}",
        f"Тема: {review.topic}",
        f"Соперник: {review.opponent_name}",
        f"Позиция: {review.stance}",
        f"{review.result.icon} Результат: {review.result.label}",
        f"Рейтинг: {rating}",
        "",
        _skill_line(review, CoachingSkill.LOGIC),
        _skill_line(review, CoachingSkill.EVIDENCE),
        _skill_line(review, CoachingSkill.REBUTTAL),
        "",
        f"Итого: {_score(review.own_scores.total)}/30 · "
        f"соперник {_score(review.opponent_scores.total)}/30 · "
        f"разница {review.total_gap:+.1f}",
        f"Сильная сторона: {strongest.icon} {strongest.label}",
        f"Фокус тренировки: {focus.icon} {focus.label}",
        f"Практика: {focus.advice}",
        "",
        f"Вердикт: {review.verdict_reason}",
        f"Завершён: {review.ended_at:%Y-%m-%d %H:%M UTC}",
        "",
        "Общий прогресс: /pvp_coach",
    ]
    await message.answer("\n".join(lines))


@router.message(Command("pvp_coach"))
async def pvp_coach_command(
    message: Message,
    coaching_repository: CoachingRepository,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    summary = await coaching_repository.summary(message.from_user.id, settings.pvp_season)
    if summary is None:
        await message.answer(
            "Для coaching-отчёта нужен хотя бы один полный PvP-матч с судейскими "
            "оценками. Матчи через сдачу или тайм-аут в навыковую статистику не входят."
        )
        return

    strongest = summary.strongest_skill
    focus = summary.focus_skill
    lines = [
        f"🎓 PvP Coach — {summary.season}",
        f"Оценено матчей: {summary.analyzed_matches}/{summary.requested_window}",
        f"Результаты: {summary.wins}/{summary.draws}/{summary.losses}",
        "",
        f"🧠 Логика: {summary.averages.logic:.1f}/10",
        f"📚 Доказательства: {summary.averages.evidence:.1f}/10",
        f"🥊 Опровержение: {summary.averages.rebuttal:.1f}/10",
        f"Средний итог: {summary.averages.total:.1f}/30",
        f"Динамика: {_trend_text(summary.trend_delta)}",
        "",
        f"Сильная сторона: {strongest.icon} {strongest.label}",
        f"Главный фокус: {focus.icon} {focus.label}",
        f"Следующая тренировка: {focus.advice}",
    ]
    if summary.pro_average_total is not None and summary.con_average_total is not None:
        stronger_stance = (
            "за"
            if summary.pro_average_total >= summary.con_average_total
            else "против"
        )
        lines.extend(
            [
                "",
                f"Средний балл за позицию «за»: {summary.pro_average_total:.1f}/30",
                f"Средний балл за позицию «против»: {summary.con_average_total:.1f}/30",
                f"Сейчас сильнее позиция: {stronger_stance}",
            ]
        )
    lines.extend(["", "Последний подробный разбор: /match_review"])
    await message.answer("\n".join(lines))
