"""Add explicit project lifecycle metadata for isolated interview demos.

Revision ID: 0003_add_demo_project_lifecycle
Revises: 0002_bridge_existing_clean_v2
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_demo_project_lifecycle"
down_revision: Union[str, None] = "0002_bridge_existing_clean_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("mode", sa.String(), nullable=False, server_default="formal"),
    )
    op.add_column(
        "projects",
        sa.Column("is_ephemeral", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("projects", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("projects", sa.Column("template_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_projects_mode"), "projects", ["mode"], unique=False)
    op.create_index(op.f("ix_projects_is_ephemeral"), "projects", ["is_ephemeral"], unique=False)
    op.create_index(op.f("ix_projects_expires_at"), "projects", ["expires_at"], unique=False)
    op.create_index(op.f("ix_projects_template_id"), "projects", ["template_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_template_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_expires_at"), table_name="projects")
    op.drop_index(op.f("ix_projects_is_ephemeral"), table_name="projects")
    op.drop_index(op.f("ix_projects_mode"), table_name="projects")
    op.drop_column("projects", "template_id")
    op.drop_column("projects", "expires_at")
    op.drop_column("projects", "is_ephemeral")
    op.drop_column("projects", "mode")
