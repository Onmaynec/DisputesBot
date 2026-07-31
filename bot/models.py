from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Stance(StrEnum):
    PRO = "за"
    CON = "против"

    @property
    def opposite(self) -> "Stance":
        return Stance.CON if self is Stance.PRO else Stance.PRO


class DebateMode(StrEnum):
    DEBATE = "debate"
    TOURNAMENT = "tournament"


@dataclass(slots=True)
class DebateMessage:
    author: str
    text: str
    round_number: int | None = None


@dataclass(slots=True)
class DebateSession:
    topic: str
    role: str
    mode: DebateMode = DebateMode.DEBATE
    user_stance: Stance | None = None
    bot_stance: Stance | None = None
    history: list[DebateMessage] = field(default_factory=list)
    user_argument_count: int = 0
    last_progress_review_at: int = 0
    tournament_round: int = 1
    user_arguments_in_round: int = 0
    bot_arguments_in_round: int = 0

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
                round_number=self.tournament_round if self.mode is DebateMode.TOURNAMENT else None,
            )
        )

    def add_bot_argument(self, text: str) -> None:
        if self.mode is DebateMode.TOURNAMENT:
            self.bot_arguments_in_round += 1
        self.history.append(
            DebateMessage(
                author="bot",
                text=text,
                round_number=self.tournament_round if self.mode is DebateMode.TOURNAMENT else None,
            )
        )

    def reset_round_counters(self) -> None:
        self.user_arguments_in_round = 0
        self.bot_arguments_in_round = 0


@dataclass(slots=True, frozen=True)
class TournamentScores:
    logic: int
    argumentation: int
    creativity: int
    winner: str
    reason: str

    @property
    def total(self) -> int:
        return self.logic + self.argumentation + self.creativity
