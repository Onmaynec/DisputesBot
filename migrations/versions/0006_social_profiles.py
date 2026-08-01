"""Add opt-in public PvP profile settings.

Revision ID: 0006_social_profiles
Revises: 0005_cosmetics
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_social_profiles"
down_revision = "0005_cosmetics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_profile_settings",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_profile_settings_public",
        "pvp_profile_settings",
        ["is_public"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pvp_profile_settings_public",
        table_name="pvp_profile_settings",
    )
    op.drop_table("pvp_profile_settings")
