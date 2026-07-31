import asyncio
import json

from bot.models import TournamentScores
from bot.storage import LeaderboardStore


def test_leaderboard_keeps_best_and_average(tmp_path) -> None:
    async def scenario() -> None:
        path = tmp_path / "leaderboard.json"
        leaderboard = LeaderboardStore(path)
        await leaderboard.record_result(
            user_id=1,
            username="alice",
            display_name="Alice",
            scores=TournamentScores(7, 8, 6, "user", "Хорошо"),
        )
        await leaderboard.record_result(
            user_id=1,
            username="alice",
            display_name="Alice",
            scores=TournamentScores(9, 9, 8, "user", "Отлично"),
        )

        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data["@alice"]
        assert entry["tournaments"] == 2
        assert entry["best_total"] == 26
        assert entry["average_total"] == 23.5

    asyncio.run(scenario())
