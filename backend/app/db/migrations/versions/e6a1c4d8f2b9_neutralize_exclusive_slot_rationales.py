"""Neutralize exclusive wording in stakeholder slot rationales.

Revision ID: e6a1c4d8f2b9
Revises: d2f5a8c1e4b7
Create Date: 2026-07-14
"""

import sqlalchemy as sa
from alembic import op

revision = "e6a1c4d8f2b9"
down_revision = "d2f5a8c1e4b7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE stakeholder_slots "
            "SET rationale = regexp_replace("
            "rationale, "
            "'^只有(這個角色|這位受訪者|該角色|他們|她們|他|她)能(夠)?(直接)?"
            "(說明|說出|說清楚|提供|釐清|確認|分享|回答)?', "
            "'了解'"
            ") "
            "WHERE rationale ~ '^只有(這個角色|這位受訪者|該角色|他們|她們|他|她)能'"
        )
    )


def downgrade():
    # The original wording cannot be reconstructed safely.
    pass
