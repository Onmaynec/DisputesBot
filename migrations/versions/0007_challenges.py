"""Add durable personal PvP challenges.

Revision ID: 0007_challenges
Revises: 0006_social_profiles
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_challenges"
down_revision = "0006_social_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_challenges",
        sa.Column("challenge_id", sa.String(length=32), primary_key=True),
        sa.Column(
            "challenger_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_pvp_challenges_target_status",
        "pvp_challenges",
        ["target_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_pvp_challenges_challenger_status",
        "pvp_challenges",
        ["challenger_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_pvp_challenges_pair_status",
        "pvp_challenges",
        ["challenger_id", "target_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_pvp_challenges_pair_status", table_name="pvp_challenges")
    op.drop_index("ix_pvp_challenges_challenger_status", table_name="pvp_challenges")
    op.drop_index("ix_pvp_challenges_target_status", table_name="pvp_challenges")
    op.drop_table("pvp_challenges")
