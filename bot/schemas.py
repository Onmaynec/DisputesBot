from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import ScoreBreakdown


class ArgumentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argument: str = Field(min_length=20, max_length=1800)


class ProgressReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strong_points: list[str] = Field(min_length=1, max_length=3)
    weak_points: list[str] = Field(min_length=1, max_length=3)
    next_move: str = Field(min_length=10, max_length=500)


class SummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_theses: list[str] = Field(default_factory=list, max_length=6)
    bot_theses: list[str] = Field(default_factory=list, max_length=6)
    agreements: list[str] = Field(default_factory=list, max_length=4)
    main_disagreement: str = Field(min_length=1, max_length=500)


class AnonymousJudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    winner: Literal["A", "B", "draw"]
    participant_a: ScoreBreakdown
    participant_b: ScoreBreakdown
    reasoning: str = Field(min_length=20, max_length=900)
    decisive_point: str = Field(min_length=5, max_length=400)


class RoundFeedbackOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strong_move: str = Field(min_length=5, max_length=500)
    weakness: str = Field(min_length=5, max_length=500)
    next_round_advice: str = Field(min_length=5, max_length=500)


class AnonymousTournamentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_a_logic: int = Field(ge=0, le=10)
    participant_a_argumentation: int = Field(ge=0, le=10)
    participant_a_creativity: int = Field(ge=0, le=10)
    participant_b_logic: int = Field(ge=0, le=10)
    participant_b_argumentation: int = Field(ge=0, le=10)
    participant_b_creativity: int = Field(ge=0, le=10)
    winner: Literal["A", "B", "draw"]
    reasoning: str = Field(min_length=20, max_length=900)
