"""Add seasonal PvP pass reward claims.

Revision ID: 0011_season_pass
Revises: 0010_goal_rewards
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_season_pass"
down_revision = "0010_goal_rewards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_season_pass_claims",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("tier_id", sa.String(length=24), primary_key=True),
        sa.Column("points_required", sa.Integer(), nullable=False),
        sa.Column("reward_tokens", sa.Integer(), nullable=False),
        sa.Column("claimed_points", sa.Integer(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_season_pass_claims_user_season_claimed",
        "pvp_season_pass_claims",
        ["user_id", "season", "claimed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pvp_season_pass_claims_user_season_claimed",
        table_name="pvp_season_pass_claims",
    )
    op.drop_table("pvp_season_pass_claims")
