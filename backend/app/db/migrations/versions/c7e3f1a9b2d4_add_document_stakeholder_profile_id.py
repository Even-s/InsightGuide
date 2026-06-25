"""Add stakeholder_profile_id to documents table.

Revision ID: c7e3f1a9b2d4
"""

import sqlalchemy as sa
from alembic import op

revision = "c7e3f1a9b2d4"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("stakeholder_profile_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_documents_stakeholder_profile_id",
        "documents",
        ["stakeholder_profile_id"],
    )
    op.create_foreign_key(
        "fk_documents_stakeholder_profile_id",
        "documents",
        "stakeholder_profiles",
        ["stakeholder_profile_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_stakeholder_profile_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_stakeholder_profile_id", table_name="documents")
    op.drop_column("documents", "stakeholder_profile_id")
