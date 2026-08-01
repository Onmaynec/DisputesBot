"""Add seasonal PvP cosmetic inventory and loadouts.

Revision ID: 0005_cosmetics
Revises: 0004_progression
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_cosmetics"
down_revision = "0004_progression"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_cosmetics",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("item_id", sa.String(length=48), primary_key=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "purchased_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_cosmetics_user_season",
        "pvp_cosmetics",
        ["user_id", "season"],
    )
    op.create_index(
        "ix_pvp_cosmetics_season_item",
        "pvp_cosmetics",
        ["season", "item_id"],
    )

    op.create_table(
        "pvp_cosmetic_loadouts",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("title_id", sa.String(length=48), nullable=True),
        sa.Column("badge_id", sa.String(length=48), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("pvp_cosmetic_loadouts")
    op.drop_index("ix_pvp_cosmetics_season_item", table_name="pvp_cosmetics")
    op.drop_index("ix_pvp_cosmetics_user_season", table_name="pvp_cosmetics")
    op.drop_table("pvp_cosmetics")
