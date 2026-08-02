from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CoachingSkill(StrEnum):
    LOGIC = "logic"
    EVIDENCE = "evidence"
    REBUTTAL = "rebuttal"

    @property
    def label(self) -> str:
        return {
            CoachingSkill.LOGIC: "Логика",
            CoachingSkill.EVIDENCE: "Доказательства",
            CoachingSkill.REBUTTAL: "Опровержение",
        }[self]

    @property
    def icon(self) -> str:
        return {
            CoachingSkill.LOGIC: "🧠",
            CoachingSkill.EVIDENCE: "📚",
            CoachingSkill.REBUTTAL: "🥊",
        }[self]

    @property
    def advice(self) -> str:
        return {
            CoachingSkill.LOGIC: (
                "Связывайте тезис, причину и вывод в одну явную цепочку и проверяйте, "
                "следует ли заключение из приведённых посылок."
            ),
            CoachingSkill.EVIDENCE: (
                "Подкрепляйте ключевые тезисы конкретными фактами, примерами или "
                "проверяемыми источниками и объясняйте, почему они релевантны."
            ),
            CoachingSkill.REBUTTAL: (
                "Сначала точно сформулируйте сильнейший довод соперника, затем отвечайте "
                "на его основание, а не только повторяйте собственную позицию."
            ),
        }[self]


class CoachingResult(StrEnum):
    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"

    @property
    def label(self) -> str:
        return {
            CoachingResult.WIN: "Победа",
            CoachingResult.DRAW: "Ничья",
            CoachingResult.LOSS: "Поражение",
        }[self]

    @property
    def icon(self) -> str:
        return {
            CoachingResult.WIN: "🏆",
            CoachingResult.DRAW: "🤝",
            CoachingResult.LOSS: "📉",
        }[self]


@dataclass(frozen=True, slots=True)
class SkillScores:
    logic: float
    evidence: float
    rebuttal: float

    @property
    def total(self) -> float:
        return self.logic + self.evidence + self.rebuttal

    def value(self, skill: CoachingSkill) -> float:
        return {
            CoachingSkill.LOGIC: self.logic,
            CoachingSkill.EVIDENCE: self.evidence,
            CoachingSkill.REBUTTAL: self.rebuttal,
        }[skill]

    @property
    def strongest_skill(self) -> CoachingSkill:
        return max(CoachingSkill, key=self.value)

    @property
    def focus_skill(self) -> CoachingSkill:
        return min(CoachingSkill, key=self.value)


@dataclass(frozen=True, slots=True)
class MatchReview:
    match_id: str
    season: str
    topic: str
    opponent_user_id: int
    opponent_name: str
    stance: str
    result: CoachingResult
    rated: bool
    rating_delta: int
    own_scores: SkillScores
    opponent_scores: SkillScores
    verdict_reason: str
    ended_at: datetime

    @property
    def total_gap(self) -> float:
        return self.own_scores.total - self.opponent_scores.total


@dataclass(frozen=True, slots=True)
class CoachingSummary:
    season: str
    analyzed_matches: int
    requested_window: int
    averages: SkillScores
    wins: int
    draws: int
    losses: int
    trend_delta: float | None
    pro_average_total: float | None
    con_average_total: float | None

    @property
    def strongest_skill(self) -> CoachingSkill:
        return self.averages.strongest_skill

    @property
    def focus_skill(self) -> CoachingSkill:
        return self.averages.focus_skill
