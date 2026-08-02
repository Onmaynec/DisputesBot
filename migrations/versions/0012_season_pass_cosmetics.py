"""Track cosmetic rewards granted by the seasonal PvP pass.

Revision ID: 0012_season_pass_cosmetics
Revises: 0011_season_pass
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_season_pass_cosmetics"
down_revision = "0011_season_pass"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pvp_season_pass_claims",
        sa.Column("reward_item_id", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "pvp_season_pass_claims",
        sa.Column("cosmetic_granted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pvp_season_pass_claims", "cosmetic_granted_at")
    op.drop_column("pvp_season_pass_claims", "reward_item_id")
