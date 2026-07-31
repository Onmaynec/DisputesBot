from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .models import DebateMode, DebateSession, Difficulty, TournamentScores

DEFAULT_ROLE = "философ"
DEFAULT_DIFFICULTY = Difficulty.EXPERIENCED


class SessionStore(Protocol):
    async def get_session(self, user_id: int) -> DebateSession | None: ...

    async def create_session(
        self,
        user_id: int,
        topic: str,
        mode: DebateMode = DebateMode.DEBATE,
    ) -> DebateSession: ...

    async def save_session(self, user_id: int, session: DebateSession) -> None: ...

    async def delete_session(self, user_id: int) -> None: ...

    async def set_role(self, user_id: int, role: str) -> None: ...

    async def set_difficulty(self, user_id: int, difficulty: Difficulty) -> None: ...

    async def set_tournament_choices(self, user_id: int, topics: list[str]) -> None: ...

    async def pop_tournament_choices(self, user_id: int) -> list[str] | None: ...

    async def close(self) -> None: ...


class MemoryStore:
    """Async in-memory implementation used by tests and local fallback scenarios."""

    def __init__(self) -> None:
        self.sessions: dict[int, DebateSession] = {}
        self.roles: dict[int, str] = {}
        self.difficulties: dict[int, Difficulty] = {}
        self.tournament_choices: dict[int, list[str]] = {}

    async def get_session(self, user_id: int) -> DebateSession | None:
        session = self.sessions.get(user_id)
        return session.model_copy(deep=True) if session else None

    async def create_session(
        self,
        user_id: int,
        topic: str,
        mode: DebateMode = DebateMode.DEBATE,
    ) -> DebateSession:
        session = DebateSession(
            topic=topic.strip(),
            role=self.roles.get(user_id, DEFAULT_ROLE),
            difficulty=self.difficulties.get(user_id, DEFAULT_DIFFICULTY),
            mode=mode,
        )
        self.sessions[user_id] = session.model_copy(deep=True)
        return session

    async def save_session(self, user_id: int, session: DebateSession) -> None:
        self.sessions[user_id] = session.model_copy(deep=True)

    async def delete_session(self, user_id: int) -> None:
        self.sessions.pop(user_id, None)
        self.tournament_choices.pop(user_id, None)

    async def set_role(self, user_id: int, role: str) -> None:
        self.roles[user_id] = role
        session = self.sessions.get(user_id)
        if session:
            session.role = role

    async def set_difficulty(self, user_id: int, difficulty: Difficulty) -> None:
        self.difficulties[user_id] = difficulty
        session = self.sessions.get(user_id)
        if session:
            session.difficulty = difficulty

    async def set_tournament_choices(self, user_id: int, topics: list[str]) -> None:
        self.tournament_choices[user_id] = list(topics)

    async def pop_tournament_choices(self, user_id: int) -> list[str] | None:
        return self.tournament_choices.pop(user_id, None)

    async def close(self) -> None:
        return None


class RedisStore:
    """Redis-backed user preferences, active sessions and tournament choices."""

    def __init__(
        self,
        redis: Any,
        *,
        session_ttl_seconds: int = 604_800,
        choice_ttl_seconds: int = 900,
        prefix: str = "disputesbot",
    ) -> None:
        self.redis = redis
        self.session_ttl_seconds = session_ttl_seconds
        self.choice_ttl_seconds = choice_ttl_seconds
        self.prefix = prefix

    def _key(self, kind: str, user_id: int) -> str:
        return f"{self.prefix}:{kind}:{user_id}"

    async def get_session(self, user_id: int) -> DebateSession | None:
        raw = await self.redis.get(self._key("session", user_id))
        if raw is None:
            return None
        try:
            return DebateSession.model_validate_json(raw)
        except ValueError:
            await self.redis.delete(self._key("session", user_id))
            return None

    async def create_session(
        self,
        user_id: int,
        topic: str,
        mode: DebateMode = DebateMode.DEBATE,
    ) -> DebateSession:
        role_raw, difficulty_raw = await self.redis.mget(
            self._key("role", user_id),
            self._key("difficulty", user_id),
        )
        role = self._decode(role_raw) or DEFAULT_ROLE
        try:
            difficulty = Difficulty(self._decode(difficulty_raw) or DEFAULT_DIFFICULTY.value)
        except ValueError:
            difficulty = DEFAULT_DIFFICULTY
        session = DebateSession(
            topic=topic.strip(),
            role=role,
            difficulty=difficulty,
            mode=mode,
        )
        await self.save_session(user_id, session)
        return session

    async def save_session(self, user_id: int, session: DebateSession) -> None:
        await self.redis.set(
            self._key("session", user_id),
            session.model_dump_json(),
            ex=self.session_ttl_seconds,
        )

    async def delete_session(self, user_id: int) -> None:
        await self.redis.delete(
            self._key("session", user_id),
            self._key("choices", user_id),
        )

    async def set_role(self, user_id: int, role: str) -> None:
        await self.redis.set(self._key("role", user_id), role)
        session = await self.get_session(user_id)
        if session:
            session.role = role
            await self.save_session(user_id, session)

    async def set_difficulty(self, user_id: int, difficulty: Difficulty) -> None:
        await self.redis.set(self._key("difficulty", user_id), difficulty.value)
        session = await self.get_session(user_id)
        if session:
            session.difficulty = difficulty
            await self.save_session(user_id, session)

    async def set_tournament_choices(self, user_id: int, topics: list[str]) -> None:
        await self.redis.set(
            self._key("choices", user_id),
            json.dumps(topics, ensure_ascii=False),
            ex=self.choice_ttl_seconds,
        )

    async def pop_tournament_choices(self, user_id: int) -> list[str] | None:
        key = self._key("choices", user_id)
        raw = await self.redis.getdel(key)
        if raw is None:
            return None
        try:
            payload = json.loads(self._decode(raw) or "[]")
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, list) and all(isinstance(x, str) for x in payload) else None

    async def close(self) -> None:
        await self.redis.aclose()

    @staticmethod
    def _decode(value: Any) -> str | None:
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)


class LeaderboardStore:
    """JSON leaderboard keyed by immutable Telegram user_id with atomic writes."""

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
            key = str(user_id)
            previous = data.get(key, {})
            tournaments = int(previous.get("tournaments", 0)) + 1
            previous_total = float(previous.get("average_total", 0)) * (tournaments - 1)
            average_total = round((previous_total + scores.total) / tournaments, 2)
            wins = int(previous.get("wins", 0)) + int(scores.winner == "user")
            draws = int(previous.get("draws", 0)) + int(scores.winner == "draw")
            losses = int(previous.get("losses", 0)) + int(scores.winner == "bot")

            entry = {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "tournaments": tournaments,
                "wins": wins,
                "draws": draws,
                "losses": losses,
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

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        async with self._lock:
            data = await asyncio.to_thread(self._read)
        entry = data.get(str(user_id))
        return dict(entry) if isinstance(entry, dict) else None

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
        if not isinstance(payload, dict):
            return {}
        return self._migrate_legacy_keys(payload)

    @staticmethod
    def _migrate_legacy_keys(payload: dict[str, Any]) -> dict[str, Any]:
        migrated: dict[str, Any] = {}
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            user_id = value.get("user_id")
            normalized_key = str(user_id) if isinstance(user_id, int) else str(key)
            existing = migrated.get(normalized_key)
            if existing is None or int(value.get("tournaments", 0)) >= int(
                existing.get("tournaments", 0)
            ):
                migrated[normalized_key] = value
        return migrated

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, self.path)
