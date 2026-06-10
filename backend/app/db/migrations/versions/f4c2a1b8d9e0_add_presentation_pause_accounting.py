"""add_presentation_pause_accounting

Revision ID: f4c2a1b8d9e0
Revises: 78e7cabb32a4
Create Date: 2026-06-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4c2a1b8d9e0'
down_revision = '78e7cabb32a4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('presentation_sessions', sa.Column('paused_at', sa.DateTime(), nullable=True))
    op.add_column(
        'presentation_sessions',
        sa.Column('paused_duration_seconds', sa.Integer(), nullable=False, server_default='0'),
    )
    op.alter_column('presentation_sessions', 'paused_duration_seconds', server_default=None)


def downgrade() -> None:
    op.drop_column('presentation_sessions', 'paused_duration_seconds')
    op.drop_column('presentation_sessions', 'paused_at')
