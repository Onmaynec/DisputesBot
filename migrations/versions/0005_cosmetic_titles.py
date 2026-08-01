"""Add purchasable and equippable PvP cosmetic titles.

Revision ID: 0005_cosmetic_titles
Revises: 0004_progression
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_cosmetic_titles"
down_revision = "0004_progression"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_title_purchases",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("title_id", sa.String(length=48), primary_key=True),
        sa.Column("price_paid", sa.Integer(), nullable=False),
        sa.Column(
            "purchased_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_pvp_title_purchases_season_title",
        "pvp_title_purchases",
        ["season", "title_id"],
    )

    op.create_table(
        "pvp_title_loadouts",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column("season", sa.String(length=32), primary_key=True),
        sa.Column("equipped_title_id", sa.String(length=48), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("pvp_title_loadouts")
    op.drop_index(
        "ix_pvp_title_purchases_season_title",
        table_name="pvp_title_purchases",
    )
    op.drop_table("pvp_title_purchases")
