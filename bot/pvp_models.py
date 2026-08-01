from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .models import ScoreBreakdown, Stance


class PvPStatus(StrEnum):
    ACTIVE = "active"
    JUDGING = "judging"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PvPUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    username: str | None = Field(default=None, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)


class PvPParticipant(PvPUser):
    stance: Stance


class PvPArgument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    stance: Stance
    text: str = Field(min_length=1, max_length=2500)
    turn_number: int = Field(ge=1, le=6)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PvPMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    match_id: str = Field(default_factory=lambda: uuid4().hex, min_length=8, max_length=64)
    topic: str = Field(min_length=1, max_length=300)
    season: str = Field(min_length=1, max_length=32)
    pro: PvPParticipant
    con: PvPParticipant
    status: PvPStatus = PvPStatus.ACTIVE
    current_user_id: int | None = None
    arguments: list[PvPArgument] = Field(default_factory=list, max_length=6)
    max_arguments_per_user: int = Field(default=3, ge=1, le=3)
    winner_user_id: int | None = None
    outcome: Literal[
        "pending",
        "judged",
        "draw",
        "forfeit",
        "timeout",
        "cancelled",
    ] = "pending"
    verdict_reason: str | None = Field(default=None, max_length=1200)
    turn_deadline: datetime | None = None
    source_match_id: str | None = Field(default=None, min_length=8, max_length=64)
    rated_hint: bool = True
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_post_init(self, __context: object) -> None:
        if self.pro.user_id == self.con.user_id:
            raise ValueError("PvP participants must be different users")
        if self.pro.stance is not Stance.PRO or self.con.stance is not Stance.CON:
            raise ValueError("PvP participants must have fixed pro/con stances")
        if self.current_user_id is None and self.status is PvPStatus.ACTIVE:
            self.current_user_id = self.pro.user_id

    def participant(self, user_id: int) -> PvPParticipant:
        if self.pro.user_id == user_id:
            return self.pro
        if self.con.user_id == user_id:
            return self.con
        raise ValueError("User is not a participant of this match")

    def opponent(self, user_id: int) -> PvPParticipant:
        participant = self.participant(user_id)
        return self.con if participant.stance is Stance.PRO else self.pro

    def argument_count(self, user_id: int) -> int:
        return sum(item.user_id == user_id for item in self.arguments)

    @property
    def is_ready_for_judging(self) -> bool:
        return self.status is PvPStatus.JUDGING and len(self.arguments) == 6

    @property
    def can_cancel_without_rating(self) -> bool:
        return self.status is PvPStatus.ACTIVE and not self.arguments

    def renew_deadline(
        self,
        timeout_seconds: int,
        *,
        now: datetime | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Turn timeout must be positive")
        if self.status is not PvPStatus.ACTIVE:
            self.turn_deadline = None
            return
        reference = now or datetime.now(UTC)
        self.turn_deadline = reference + timedelta(seconds=timeout_seconds)
        self.updated_at = reference

    def seconds_until_deadline(self, *, now: datetime | None = None) -> int | None:
        if self.turn_deadline is None or self.status is not PvPStatus.ACTIVE:
            return None
        reference = now or datetime.now(UTC)
        return max(0, int((self.turn_deadline - reference).total_seconds()))

    def is_expired(self, *, now: datetime | None = None) -> bool:
        if self.turn_deadline is None or self.status is not PvPStatus.ACTIVE:
            return False
        return self.turn_deadline <= (now or datetime.now(UTC))

    def add_argument(
        self,
        user_id: int,
        text: str,
        *,
        turn_timeout_seconds: int | None = None,
    ) -> None:
        if self.status is not PvPStatus.ACTIVE:
            raise ValueError("Match is not accepting arguments")
        participant = self.participant(user_id)
        if self.current_user_id != user_id:
            raise ValueError("It is not this participant's turn")
        normalized = text.strip()
        if not normalized:
            raise ValueError("Argument cannot be empty")
        if len(normalized) > 2500:
            raise ValueError("Argument is too long")
        if self.argument_count(user_id) >= self.max_arguments_per_user:
            raise ValueError("Participant has already used all arguments")

        self.arguments.append(
            PvPArgument(
                user_id=user_id,
                stance=participant.stance,
                text=normalized,
                turn_number=len(self.arguments) + 1,
            )
        )
        self.updated_at = datetime.now(UTC)
        if len(self.arguments) >= self.max_arguments_per_user * 2:
            self.status = PvPStatus.JUDGING
            self.current_user_id = None
            self.turn_deadline = None
        else:
            self.current_user_id = self.opponent(user_id).user_id
            if turn_timeout_seconds is not None:
                self.renew_deadline(turn_timeout_seconds)

    def cancel(self) -> None:
        if not self.can_cancel_without_rating:
            raise ValueError("Only an unstarted match can be cancelled")
        self.status = PvPStatus.CANCELLED
        self.outcome = "cancelled"
        self.current_user_id = None
        self.turn_deadline = None
        self.updated_at = datetime.now(UTC)

    def forfeit(self, user_id: int) -> int:
        return self._complete_loss(user_id, "forfeit", "сдался")

    def timeout(self, user_id: int) -> int:
        if self.status is not PvPStatus.ACTIVE:
            raise ValueError("Only an active match can time out")
        if self.current_user_id != user_id:
            raise ValueError("Only the current participant can time out")
        return self._complete_loss(user_id, "timeout", "не сделал ход вовремя")

    def _complete_loss(
        self,
        user_id: int,
        outcome: Literal["forfeit", "timeout"],
        verb: str,
    ) -> int:
        if self.status not in {PvPStatus.ACTIVE, PvPStatus.JUDGING}:
            raise ValueError("Match is already finished")
        winner = self.opponent(user_id)
        loser = self.participant(user_id)
        self.status = PvPStatus.COMPLETED
        self.current_user_id = None
        self.turn_deadline = None
        self.winner_user_id = winner.user_id
        self.outcome = outcome
        self.verdict_reason = f"Участник {loser.display_name} {verb}."
        self.updated_at = datetime.now(UTC)
        return winner.user_id

    def complete_judging(self, winner_user_id: int | None, reason: str) -> None:
        if self.status is not PvPStatus.JUDGING:
            raise ValueError("Match is not awaiting judging")
        if winner_user_id is not None:
            self.participant(winner_user_id)
        self.status = PvPStatus.COMPLETED
        self.current_user_id = None
        self.turn_deadline = None
        self.winner_user_id = winner_user_id
        self.outcome = "draw" if winner_user_id is None else "judged"
        self.verdict_reason = reason
        self.updated_at = datetime.now(UTC)


class PvPJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    winner_user_id: int | None
    pro_scores: ScoreBreakdown
    con_scores: ScoreBreakdown
    reasoning: str = Field(min_length=20, max_length=900)
    decisive_point: str = Field(min_length=5, max_length=400)


class PvPQueueEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant: PvPUser
    topic: str = Field(min_length=1, max_length=300)
    season: str = Field(min_length=1, max_length=32)
    queued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PvPInvitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(default_factory=lambda: uuid4().hex, min_length=8, max_length=64)
    inviter: PvPUser
    topic: str = Field(min_length=1, max_length=300)
    season: str = Field(min_length=1, max_length=32)
    target_user_id: int | None = None
    source_match_id: str | None = Field(default=None, min_length=8, max_length=64)
    rated_hint: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PvPMatchHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    season: str
    topic: str
    pro_user_id: int
    con_user_id: int
    winner_user_id: int | None
    outcome: Literal["judged", "draw", "forfeit", "timeout"]
    pro_rating_before: int
    pro_rating_after: int
    con_rating_before: int
    con_rating_after: int
    rated: bool = True
    unrated_reason: str | None = None
    reason: str
    started_at: datetime
    ended_at: datetime
