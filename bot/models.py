from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Stance(StrEnum):
    PRO = "за"
    CON = "против"

    @property
    def opposite(self) -> Stance:
        return Stance.CON if self is Stance.PRO else Stance.PRO


class DebateMode(StrEnum):
    DEBATE = "debate"
    TOURNAMENT = "tournament"


class Difficulty(StrEnum):
    BEGINNER = "новичок"
    EXPERIENCED = "опытный"
    EXPERT = "эксперт"


class DebateMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: Literal["user", "bot"]
    text: str
    round_number: int | None = None


class DebateSession(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    topic: str
    role: str
    difficulty: Difficulty = Difficulty.EXPERIENCED
    mode: DebateMode = DebateMode.DEBATE
    user_stance: Stance | None = None
    bot_stance: Stance | None = None
    history: list[DebateMessage] = Field(default_factory=list)
    user_argument_count: int = 0
    last_progress_review_at: int = 0
    tournament_round: int = 1
    user_arguments_in_round: int = 0
    bot_arguments_in_round: int = 0
    awaiting_final_score: bool = False
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    archive_id: str | None = None
    last_fallacies: list[str] = Field(default_factory=list, max_length=10)

    @property
    def is_waiting_for_stance(self) -> bool:
        return self.user_stance is None

    def set_stance(self, user_stance: Stance) -> None:
        self.user_stance = user_stance
        self.bot_stance = user_stance.opposite
        self.history.append(
            DebateMessage(author="user", text=f"Позиция пользователя: {user_stance.value}")
        )

    def add_user_argument(self, text: str) -> None:
        self.user_argument_count += 1
        if self.mode is DebateMode.TOURNAMENT:
            self.user_arguments_in_round += 1
        self.history.append(
            DebateMessage(
                author="user",
                text=text,
                round_number=self.tournament_round
                if self.mode is DebateMode.TOURNAMENT
                else None,
            )
        )

    def add_bot_argument(self, text: str) -> None:
        if self.mode is DebateMode.TOURNAMENT:
            self.bot_arguments_in_round += 1
        self.history.append(
            DebateMessage(
                author="bot",
                text=text,
                round_number=self.tournament_round
                if self.mode is DebateMode.TOURNAMENT
                else None,
            )
        )

    def reset_round_counters(self) -> None:
        self.user_arguments_in_round = 0
        self.bot_arguments_in_round = 0


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logic: int = Field(ge=0, le=10)
    evidence: int = Field(ge=0, le=10)
    rebuttal: int = Field(ge=0, le=10)

    @property
    def total(self) -> int:
        return self.logic + self.evidence + self.rebuttal


class TournamentScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logic: int = Field(ge=0, le=10)
    argumentation: int = Field(ge=0, le=10)
    creativity: int = Field(ge=0, le=10)
    winner: Literal["user", "bot", "draw"]
    reason: str = Field(min_length=1, max_length=600)

    @property
    def total(self) -> int:
        return self.logic + self.argumentation + self.creativity


class DebateArchiveEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid4().hex)
    topic: str
    mode: DebateMode
    role: str
    difficulty: Difficulty
    status: Literal["judged", "cancelled", "completed", "replaced"]
    winner: Literal["user", "bot", "draw", "none"] = "none"
    score_total: int | None = Field(default=None, ge=0, le=30)
    user_argument_count: int = Field(ge=0)
    user_stance: Stance | None = None
    started_at: datetime
    ended_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    fallacies: list[str] = Field(default_factory=list, max_length=10)
    transcript: list[DebateMessage] = Field(default_factory=list, max_length=80)

    @classmethod
    def from_session(
        cls,
        session: DebateSession,
        *,
        status: Literal["judged", "cancelled", "completed", "replaced"],
        winner: Literal["user", "bot", "draw", "none"] = "none",
        score_total: int | None = None,
    ) -> DebateArchiveEntry:
        return cls(
            id=session.archive_id or session.session_id,
            topic=session.topic,
            mode=session.mode,
            role=session.role,
            difficulty=session.difficulty,
            status=status,
            winner=winner,
            score_total=score_total,
            user_argument_count=session.user_argument_count,
            user_stance=session.user_stance,
            started_at=session.started_at,
            fallacies=list(session.last_fallacies),
            transcript=session.history[-80:],
        )
