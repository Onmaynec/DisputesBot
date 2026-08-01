"""Add daily PvP quests, seasonal progression and reward claims.

Revision ID: 0004_progression
Revises: 0003_moderation
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_progression"
down_revision = "0003_moderation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_progression",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("season_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_claims", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "current_daily_streak",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "best_daily_streak",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_claim_date", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_progression_season_points",
        "pvp_progression",
        ["season", "season_points"],
    )

    op.create_table(
        "pvp_daily_claims",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("quest_id", sa.String(length=48), primary_key=True),
        sa.Column("reward_tokens", sa.Integer(), nullable=False),
        sa.Column("reward_points", sa.Integer(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_daily_claims_season_day",
        "pvp_daily_claims",
        ["season", "day"],
    )
    op.create_index(
        "ix_pvp_daily_claims_user_day",
        "pvp_daily_claims",
        ["user_id", "day"],
    )


def downgrade() -> None:
    op.drop_index("ix_pvp_daily_claims_user_day", table_name="pvp_daily_claims")
    op.drop_index("ix_pvp_daily_claims_season_day", table_name="pvp_daily_claims")
    op.drop_table("pvp_daily_claims")
    op.drop_index("ix_pvp_progression_season_points", table_name="pvp_progression")
    op.drop_table("pvp_progression")
