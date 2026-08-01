"""Add PvP moderation, pair rating policy and report audit.

Revision ID: 0003_moderation
Revises: 0002_pvp
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_moderation"
down_revision = "0002_pvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pvp_matches",
        sa.Column("pair_key", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "pvp_matches",
        sa.Column("rated", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "pvp_matches",
        sa.Column("unrated_reason", sa.String(length=255), nullable=True),
    )
    op.execute(
        "UPDATE pvp_matches SET pair_key = "
        "CAST(LEAST(pro_user_id, con_user_id) AS TEXT) || ':' || "
        "CAST(GREATEST(pro_user_id, con_user_id) AS TEXT) "
        "WHERE pair_key IS NULL"
    )
    op.create_index(
        "ix_pvp_matches_pair_ended",
        "pvp_matches",
        ["pair_key", "ended_at"],
    )

    op.create_table(
        "pvp_blocks",
        sa.Column(
            "blocker_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column(
            "blocked_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column(
            "blocked_label",
            sa.String(length=255),
            nullable=False,
            server_default="Пользователь",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_pvp_blocks_blocked", "pvp_blocks", ["blocked_id"])

    op.create_table(
        "pvp_reports",
        sa.Column("report_id", sa.String(length=64), primary_key=True),
        sa.Column("match_id", sa.String(length=64), nullable=False),
        sa.Column("match_topic", sa.Text(), nullable=False),
        sa.Column("reporter_id", sa.BigInteger(), nullable=True),
        sa.Column("opponent_user_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="open",
        ),
        sa.Column("moderator_id", sa.BigInteger(), nullable=True),
        sa.Column("moderation_note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_pvp_reports_status_created",
        "pvp_reports",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_pvp_reports_reporter_created",
        "pvp_reports",
        ["reporter_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pvp_reports_reporter_created", table_name="pvp_reports")
    op.drop_index("ix_pvp_reports_status_created", table_name="pvp_reports")
    op.drop_table("pvp_reports")
    op.drop_index("ix_pvp_blocks_blocked", table_name="pvp_blocks")
    op.drop_table("pvp_blocks")
    op.drop_index("ix_pvp_matches_pair_ended", table_name="pvp_matches")
    op.drop_column("pvp_matches", "unrated_reason")
    op.drop_column("pvp_matches", "rated")
    op.drop_column("pvp_matches", "pair_key")
