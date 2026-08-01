"""Create PostgreSQL profiles and debate archives.

Revision ID: 0001_profiles
Revises:
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_profiles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("tournaments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("regular_debates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_debates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("score_totals", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallacy_analyses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallacy_counts", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("achievements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_user_profiles_ranking",
        "user_profiles",
        ["best_total", "average_total"],
    )
    op.create_table(
        "debate_archives",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("difficulty", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("winner", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("score_total", sa.Integer(), nullable=True),
        sa.Column("user_argument_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_stance", sa.String(length=16), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fallacies", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("transcript", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index(
        "ix_debate_archives_user_ended",
        "debate_archives",
        ["user_id", "ended_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_debate_archives_user_ended", table_name="debate_archives")
    op.drop_table("debate_archives")
    op.drop_index("ix_user_profiles_ranking", table_name="user_profiles")
    op.drop_table("user_profiles")
