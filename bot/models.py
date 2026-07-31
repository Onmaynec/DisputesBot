from __future__ import annotations

from enum import StrEnum
from typing import Literal

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
