from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReportCategory(StrEnum):
    ABUSE = "оскорбления"
    SPAM = "спам"
    CHEATING = "обход_правил"
    OTHER = "другое"


class ReportStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class BlockedUserView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    label: str
    created_at: datetime


class PvPReportView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    match_id: str
    match_topic: str
    reporter_id: int | None
    opponent_user_id: int
    category: ReportCategory
    comment: str = Field(max_length=500)
    status: ReportStatus
    moderator_id: int | None
    moderation_note: str | None
    created_at: datetime
    resolved_at: datetime | None
