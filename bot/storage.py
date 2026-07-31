from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import DebateMode, DebateSession, TournamentScores


DEFAULT_ROLE = "философ"


class MemoryStore:
    """In-memory state, intentionally reset when the process restarts."""

    def __init__(self) -> None:
        self.sessions: dict[int, DebateSession] = {}
        self.roles: dict[int, str] = {}
        self.tournament_choices: dict[int, list[str]] = {}

    def get_session(self, user_id: int) -> DebateSession | None:
        return self.sessions.get(user_id)

    def create_session(
        self,
        user_id: int,
        topic: str,
        mode: DebateMode = DebateMode.DEBATE,
    ) -> DebateSession:
        session = DebateSession(
            topic=topic.strip(),
            role=self.roles.get(user_id, DEFAULT_ROLE),
            mode=mode,
        )
        self.sessions[user_id] = session
        return session

    def set_role(self, user_id: int, role: str) -> None:
        self.roles[user_id] = role
        session = self.sessions.get(user_id)
        if session is not None:
            session.role = role


class LeaderboardStore:
    """Small JSON leaderboard with atomic writes and an async process lock."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    async def record_result(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        scores: TournamentScores,
    ) -> dict[str, Any]:
        async with self._lock:
            data = await asyncio.to_thread(self._read)
            key = f"@{username}" if username else f"user_{user_id}"
            previous = data.get(key, {})
            tournaments = int(previous.get("tournaments", 0)) + 1
            previous_total = float(previous.get("average_total", 0)) * (tournaments - 1)
            average_total = round((previous_total + scores.total) / tournaments, 2)

            entry = {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "tournaments": tournaments,
                "best_total": max(int(previous.get("best_total", 0)), scores.total),
                "average_total": average_total,
                "last_scores": {
                    "logic": scores.logic,
                    "argumentation": scores.argumentation,
                    "creativity": scores.creativity,
                    "total": scores.total,
                },
                "updated_at": datetime.now(UTC).isoformat(),
            }
            data[key] = entry
            await asyncio.to_thread(self._write, data)
            return entry

    async def top(self, limit: int = 10) -> list[tuple[str, dict[str, Any]]]:
        async with self._lock:
            data = await asyncio.to_thread(self._read)
        return sorted(
            data.items(),
            key=lambda item: (
                int(item[1].get("best_total", 0)),
                float(item[1].get("average_total", 0)),
                int(item[1].get("tournaments", 0)),
            ),
            reverse=True,
        )[:limit]

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, self.path)
