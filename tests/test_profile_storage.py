import json
from pathlib import Path

from bot.models import DebateMode, DebateSession, Stance, TournamentScores
from bot.profile_store import ProfileStore
from bot.storage import MemoryStore


async def test_profile_migrates_v02_leaderboard(tmp_path: Path) -> None:
    path = tmp_path / "leaderboard.json"
    path.write_text(
        json.dumps(
            {
                "@alice": {
                    "user_id": 1,
                    "username": "alice",
                    "display_name": "Alice",
                    "tournaments": 2,
                    "best_total": 24,
                    "average_total": 22.5,
                }
            }
        ),
        encoding="utf-8",
    )
    store = ProfileStore(path, MemoryStore())

    profile = await store.get_user(1)

    assert profile is not None
    assert profile["tournaments"] == 2
    assert profile["completed_debates"] == 2
    assert profile["xp"] == 60
    assert "first_tournament" in profile["achievements"]


async def test_tournament_updates_progress_and_archives_session(tmp_path: Path) -> None:
    sessions = MemoryStore()
    store = ProfileStore(tmp_path / "leaderboard.json", sessions)
    session = await sessions.create_session(1, "Тема", DebateMode.TOURNAMENT)
    session.add_user_argument("Аргумент")
    await sessions.save_session(1, session)
    scores = TournamentScores(
        logic=9,
        argumentation=8,
        creativity=7,
        winner="user",
        reason="Сильное выступление",
    )

    profile = await store.record_result(
        user_id=1,
        username="alice",
        display_name="Alice",
        scores=scores,
    )

    assert profile["tournaments"] == 1
    assert profile["wins"] == 1
    assert profile["best_total"] == 24
    assert profile["current_streak"] == 1
    assert profile["score_totals"]["logic"] == 9
    assert len(profile["history"]) == 1
    assert profile["history"][0]["topic"] == "Тема"


async def test_archive_is_idempotent_and_preserves_verdict(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "leaderboard.json", MemoryStore())
    session = DebateSession(topic="Тема", role="философ")
    session.set_stance(Stance.PRO)
    session.add_user_argument("Аргумент")

    first = await store.archive_debate(
        user_id=1,
        username="alice",
        display_name="Alice",
        session=session,
        status="judged",
        winner="draw",
        score_total=21,
    )
    session.add_user_argument("Ещё один аргумент")
    second = await store.archive_debate(
        user_id=1,
        username="alice",
        display_name="Alice",
        session=session,
        status="cancelled",
    )

    assert first["completed_debates"] == 1
    assert second["completed_debates"] == 1
    assert len(second["history"]) == 1
    assert second["history"][0]["winner"] == "draw"
    assert second["history"][0]["score_total"] == 21
    assert second["history"][0]["user_argument_count"] == 2


async def test_history_returns_newest_first(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "leaderboard.json", MemoryStore())
    for topic in ("Первая", "Вторая"):
        session = DebateSession(topic=topic, role="философ")
        session.add_user_argument("Аргумент")
        await store.archive_debate(
            user_id=1,
            username=None,
            display_name="Alice",
            session=session,
            status="cancelled",
        )

    history = await store.history(1, limit=2)
    last = await store.last_debate(1)

    assert [item.topic for item in history] == ["Вторая", "Первая"]
    assert last is not None
    assert last.topic == "Вторая"


async def test_fallacy_analysis_unlocks_achievement(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "leaderboard.json", MemoryStore())
    profile = {}
    for _ in range(3):
        profile = await store.record_fallacy_analysis(
            user_id=1,
            username="alice",
            display_name="Alice",
            names=["Ложная дилемма"],
        )

    assert profile["fallacy_counts"]["ложная дилемма"] == 3
    assert "fallacy_hunter" in profile["achievements"]
    assert "fallacy_hunter" in profile["new_achievements"]
