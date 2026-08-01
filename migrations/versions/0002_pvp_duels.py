"""Add PvP seasonal ratings and completed matches.

Revision ID: 0002_pvp
Revises: 0001_profiles
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_pvp"
down_revision = "0001_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_players",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("games", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_players_season_rating",
        "pvp_players",
        ["season", "rating"],
    )
    op.create_table(
        "pvp_matches",
        sa.Column("match_id", sa.String(length=64), primary_key=True),
        sa.Column("season", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column(
            "pro_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "con_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("winner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("pro_rating_before", sa.Integer(), nullable=False),
        sa.Column("pro_rating_after", sa.Integer(), nullable=False),
        sa.Column("con_rating_before", sa.Integer(), nullable=False),
        sa.Column("con_rating_after", sa.Integer(), nullable=False),
        sa.Column("pro_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("con_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("transcript", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_pvp_matches_pro_ended",
        "pvp_matches",
        ["pro_user_id", "ended_at"],
    )
    op.create_index(
        "ix_pvp_matches_con_ended",
        "pvp_matches",
        ["con_user_id", "ended_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pvp_matches_con_ended", table_name="pvp_matches")
    op.drop_index("ix_pvp_matches_pro_ended", table_name="pvp_matches")
    op.drop_table("pvp_matches")
    op.drop_index("ix_pvp_players_season_rating", table_name="pvp_players")
    op.drop_table("pvp_players")
