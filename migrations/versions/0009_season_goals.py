"""Add private seasonal PvP goals.

Revision ID: 0009_season_goals
Revises: 0008_ranked_rewards
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_season_goals"
down_revision = "0008_ranked_rewards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_season_goals",
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_season_goals_user_season_completed",
        "pvp_season_goals",
        ["user_id", "season", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pvp_season_goals_user_season_completed",
        table_name="pvp_season_goals",
    )
    op.drop_table("pvp_season_goals")
