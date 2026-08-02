from __future__ import annotations

from dataclasses import dataclass

from .league_models import LEAGUE_CATALOG, LeagueDefinition, LeagueId, LeagueStatus


@dataclass(frozen=True, slots=True)
class RankedRewardDefinition:
    league: LeagueDefinition
    tokens: int


RANKED_REWARD_CATALOG: tuple[RankedRewardDefinition, ...] = (
    RankedRewardDefinition(LEAGUE_CATALOG[0], 15),
    RankedRewardDefinition(LEAGUE_CATALOG[1], 25),
    RankedRewardDefinition(LEAGUE_CATALOG[2], 40),
    RankedRewardDefinition(LEAGUE_CATALOG[3], 60),
    RankedRewardDefinition(LEAGUE_CATALOG[4], 90),
    RankedRewardDefinition(LEAGUE_CATALOG[5], 130),
    RankedRewardDefinition(LEAGUE_CATALOG[6], 200),
)

REWARD_BY_LEAGUE: dict[LeagueId, RankedRewardDefinition] = {
    definition.league.league_id: definition for definition in RANKED_REWARD_CATALOG
}


@dataclass(frozen=True, slots=True)
class RankedRewardEntry:
    definition: RankedRewardDefinition
    eligible: bool
    claimed: bool


@dataclass(frozen=True, slots=True)
class RankedRewardsView:
    user_id: int
    season: str
    rating: int
    games: int
    peak_rating: int
    status: LeagueStatus
    entries: tuple[RankedRewardEntry, ...]
    wallet_tokens: int

    @property
    def claimable_tokens(self) -> int:
        return sum(
            entry.definition.tokens
            for entry in self.entries
            if entry.eligible and not entry.claimed
        )


@dataclass(frozen=True, slots=True)
class RankedRewardClaimResult:
    claimed_league_ids: tuple[LeagueId, ...]
    gained_tokens: int
    wallet_tokens: int
    view: RankedRewardsView


def reward_definitions_up_to(league_id: LeagueId) -> tuple[RankedRewardDefinition, ...]:
    reached: list[RankedRewardDefinition] = []
    for definition in RANKED_REWARD_CATALOG:
        reached.append(definition)
        if definition.league.league_id is league_id:
            return tuple(reached)
    raise ValueError(f"Unknown league reward: {league_id}")
