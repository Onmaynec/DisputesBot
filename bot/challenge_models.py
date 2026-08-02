from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ChallengeStatus(StrEnum):
    PENDING = "pending"
    ACCEPTING = "accepting"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ChallengeError(RuntimeError):
    pass


class ChallengeNotFoundError(ChallengeError):
    pass


class ChallengeAccessError(ChallengeError):
    pass


class ChallengeUnavailableError(ChallengeError):
    pass


class ChallengeBlockedError(ChallengeError):
    pass


class ChallengeUnknownTargetError(ChallengeError):
    pass


@dataclass(frozen=True, slots=True)
class ChallengeUser:
    user_id: int
    display_name: str
    username: str | None = None


@dataclass(frozen=True, slots=True)
class ChallengeView:
    challenge_id: str
    challenger: ChallengeUser
    target: ChallengeUser
    season: str
    topic: str
    status: ChallengeStatus
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None
    match_id: str | None = None

    @property
    def active(self) -> bool:
        return self.status in {ChallengeStatus.PENDING, ChallengeStatus.ACCEPTING}


@dataclass(frozen=True, slots=True)
class ChallengeInbox:
    incoming: tuple[ChallengeView, ...]
    outgoing: tuple[ChallengeView, ...]
