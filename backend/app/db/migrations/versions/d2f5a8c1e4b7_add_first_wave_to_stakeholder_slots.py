"""Add first-wave prioritization to stakeholder slots.

Revision ID: d2f5a8c1e4b7
Revises: c7e3f1a9b2d4
Create Date: 2026-07-14
"""

import sqlalchemy as sa
from alembic import op

revision = "d2f5a8c1e4b7"
down_revision = "c7e3f1a9b2d4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stakeholder_slots",
        sa.Column("first_wave", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            "UPDATE stakeholder_slots SET first_wave = true "
            "WHERE order_index < 3 AND priority = 'required'"
        )
    )


def downgrade():
    op.drop_column("stakeholder_slots", "first_wave")
