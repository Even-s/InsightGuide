"""Allow multiple interview sessions to continue the same round.

Revision ID: a9c4e7b2d5f1
Revises: f7a9c2e4b6d8
"""

import sqlalchemy as sa
from alembic import op

revision = "a9c4e7b2d5f1"
down_revision = "f7a9c2e4b6d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE interview_sessions "
        "DROP CONSTRAINT IF EXISTS uq_interview_sessions_interview_round_id"
    )
    op.add_column(
        "interview_sessions",
        sa.Column("continued_from_session_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_sessions_continued_from_session_id",
        "interview_sessions",
        "interview_sessions",
        ["continued_from_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_interview_sessions_continued_from_session_id",
        "interview_sessions",
        ["continued_from_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_sessions_continued_from_session_id",
        table_name="interview_sessions",
    )
    op.drop_constraint(
        "fk_interview_sessions_continued_from_session_id",
        "interview_sessions",
        type_="foreignkey",
    )
    op.drop_column("interview_sessions", "continued_from_session_id")
    op.create_unique_constraint(
        "uq_interview_sessions_interview_round_id",
        "interview_sessions",
        ["interview_round_id"],
    )
