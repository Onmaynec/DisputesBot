from __future__ import annotations

from typing import Any, Literal, Protocol

from .models import DebateArchiveEntry, DebateSession, TournamentScores


class ProfileRepository(Protocol):
    async def record_result(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        scores: TournamentScores,
    ) -> dict[str, Any]: ...

    async def archive_debate(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        session: DebateSession,
        status: Literal["judged", "cancelled", "replaced"],
        winner: Literal["user", "bot", "draw", "none"] = "none",
        score_total: int | None = None,
    ) -> dict[str, Any]: ...

    async def record_fallacy_analysis(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        names: list[str],
    ) -> dict[str, Any]: ...

    async def history(self, user_id: int, limit: int = 5) -> list[DebateArchiveEntry]: ...

    async def last_debate(self, user_id: int) -> DebateArchiveEntry | None: ...

    async def get_user(self, user_id: int) -> dict[str, Any] | None: ...

    async def rank(self, user_id: int) -> int | None: ...

    async def top(self, limit: int = 10) -> list[tuple[str, dict[str, Any]]]: ...

    async def delete_user(self, user_id: int) -> bool: ...
