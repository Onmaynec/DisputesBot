"""Add ranked league reward claims.

Revision ID: 0008_ranked_rewards
Revises: 0007_challenges
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_ranked_rewards"
down_revision = "0007_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_ranked_reward_claims",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("league_id", sa.String(length=24), primary_key=True),
        sa.Column("reward_tokens", sa.Integer(), nullable=False),
        sa.Column("claimed_rating", sa.Integer(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_ranked_reward_claims_season_league",
        "pvp_ranked_reward_claims",
        ["season", "league_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pvp_ranked_reward_claims_season_league",
        table_name="pvp_ranked_reward_claims",
    )
    op.drop_table("pvp_ranked_reward_claims")
