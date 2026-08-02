"""Add seasonal PvP goal reward claims.

Revision ID: 0010_goal_rewards
Revises: 0009_season_goals
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_goal_rewards"
down_revision = "0009_season_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_goal_reward_claims",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("metric", sa.String(length=24), primary_key=True),
        sa.Column("baseline_value", sa.Float(), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("reward_tokens", sa.Integer(), nullable=False),
        sa.Column("reward_points", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_goal_reward_claims_user_season_claimed",
        "pvp_goal_reward_claims",
        ["user_id", "season", "claimed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pvp_goal_reward_claims_user_season_claimed",
        table_name="pvp_goal_reward_claims",
    )
    op.drop_table("pvp_goal_reward_claims")
