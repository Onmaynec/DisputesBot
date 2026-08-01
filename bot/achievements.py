from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class Achievement:
    id: str
    emoji: str
    title: str
    description: str
    condition: Callable[[dict[str, Any]], bool]


ACHIEVEMENTS = (
    Achievement(
        "first_debate",
        "🗣",
        "Первый спор",
        "Завершить или сохранить первый спор.",
        lambda p: int(p.get("completed_debates", 0)) >= 1,
    ),
    Achievement(
        "five_debates",
        "🔥",
        "Разогрев",
        "Завершить пять споров.",
        lambda p: int(p.get("completed_debates", 0)) >= 5,
    ),
    Achievement(
        "first_tournament",
        "🏟",
        "Дебютант турнира",
        "Завершить первый турнир.",
        lambda p: int(p.get("tournaments", 0)) >= 1,
    ),
    Achievement(
        "first_win",
        "🏆",
        "Первая победа",
        "Победить в турнире.",
        lambda p: int(p.get("wins", 0)) >= 1,
    ),
    Achievement(
        "logic_master",
        "🧠",
        "Мастер логики",
        "Получить 9 или 10 баллов за логику.",
        lambda p: int(p.get("last_scores", {}).get("logic", 0)) >= 9,
    ),
    Achievement(
        "perfect_score",
        "💎",
        "Идеальный раунд",
        "Получить 30 из 30 в турнире.",
        lambda p: int(p.get("best_total", 0)) >= 30,
    ),
    Achievement(
        "streak_three",
        "⚡",
        "Серия побед",
        "Победить в трёх турнирах подряд.",
        lambda p: int(p.get("best_streak", 0)) >= 3,
    ),
    Achievement(
        "fallacy_hunter",
        "🔎",
        "Охотник за ошибками",
        "Трижды проанализировать логические ошибки.",
        lambda p: int(p.get("fallacy_analyses", 0)) >= 3,
    ),
    Achievement(
        "veteran",
        "🎖",
        "Ветеран",
        "Завершить десять турниров.",
        lambda p: int(p.get("tournaments", 0)) >= 10,
    ),
)

ACHIEVEMENT_BY_ID = {item.id: item for item in ACHIEVEMENTS}


def level_from_xp(xp: int) -> int:
    return max(1, xp // 100 + 1)


def level_title(level: int) -> str:
    if level >= 10:
        return "Гроссмейстер спора"
    if level >= 7:
        return "Мастер аргументации"
    if level >= 5:
        return "Оратор"
    if level >= 3:
        return "Полемист"
    if level >= 2:
        return "Ученик риторики"
    return "Новичок"


def unlock_achievements(profile: dict[str, Any]) -> list[str]:
    unlocked = set(str(item) for item in profile.get("achievements", []))
    new_ids = [
        item.id
        for item in ACHIEVEMENTS
        if item.id not in unlocked and item.condition(profile)
    ]
    if new_ids:
        profile["achievements"] = sorted(unlocked | set(new_ids))
    return new_ids
