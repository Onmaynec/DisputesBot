from pathlib import Path

from bot.league_models import LEAGUE_CATALOG, LeagueId
from bot.ranked_reward_models import (
    RANKED_REWARD_CATALOG,
    reward_definitions_up_to,
)


def test_ranked_reward_catalog_matches_league_order() -> None:
    assert [item.league.league_id for item in RANKED_REWARD_CATALOG] == [
        item.league_id for item in LEAGUE_CATALOG
    ]
    assert all(item.tokens > 0 for item in RANKED_REWARD_CATALOG)
    assert list(item.tokens for item in RANKED_REWARD_CATALOG) == sorted(
        item.tokens for item in RANKED_REWARD_CATALOG
    )


def test_reward_definitions_are_cumulative() -> None:
    reached = reward_definitions_up_to(LeagueId.PLATINUM)

    assert tuple(item.league.league_id for item in reached) == (
        LeagueId.BRONZE,
        LeagueId.SILVER,
        LeagueId.GOLD,
        LeagueId.PLATINUM,
    )
    assert sum(item.tokens for item in reached) == 140


def test_ranked_rewards_migration_follows_challenges() -> None:
    migration = Path("migrations/versions/0008_ranked_rewards.py").read_text(
        encoding="utf-8"
    )

    assert 'revision = "0008_ranked_rewards"' in migration
    assert 'down_revision = "0007_challenges"' in migration
    assert '"pvp_ranked_reward_claims"' in migration
    assert 'ondelete="CASCADE"' in migration
