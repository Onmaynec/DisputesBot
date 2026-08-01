from bot.achievements import level_from_xp, level_title, unlock_achievements


def test_level_progression() -> None:
    assert level_from_xp(0) == 1
    assert level_from_xp(99) == 1
    assert level_from_xp(100) == 2
    assert level_title(5) == "Оратор"


def test_unlock_achievements_is_idempotent() -> None:
    profile = {
        "completed_debates": 1,
        "tournaments": 1,
        "wins": 1,
        "last_scores": {"logic": 9},
        "best_total": 25,
        "best_streak": 1,
        "fallacy_analyses": 0,
        "achievements": [],
    }
    first = unlock_achievements(profile)
    second = unlock_achievements(profile)

    assert {"first_debate", "first_tournament", "first_win", "logic_master"} <= set(first)
    assert second == []
