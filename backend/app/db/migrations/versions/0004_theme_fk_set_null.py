"""Set interview session current theme to null when its theme is deleted.

Revision ID: 0004_theme_fk_set_null
Revises: 0003_add_demo_project_lifecycle
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004_theme_fk_set_null"
down_revision: Union[str, None] = "0003_add_demo_project_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "interview_sessions_current_theme_id_fkey",
        "interview_sessions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "interview_sessions_current_theme_id_fkey",
        "interview_sessions",
        "interview_themes",
        ["current_theme_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "interview_sessions_current_theme_id_fkey",
        "interview_sessions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "interview_sessions_current_theme_id_fkey",
        "interview_sessions",
        "interview_themes",
        ["current_theme_id"],
        ["id"],
    )
