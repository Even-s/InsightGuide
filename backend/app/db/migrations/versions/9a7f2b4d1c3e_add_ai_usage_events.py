"""add_ai_usage_events

Revision ID: 9a7f2b4d1c3e
Revises: f4c2a1b8d9e0
Create Date: 2026-06-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a7f2b4d1c3e'
down_revision = 'f4c2a1b8d9e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_usage_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('presentation_session_id', sa.String(), nullable=False),
        sa.Column('operation', sa.String(), nullable=False),
        sa.Column('source_id', sa.String(), nullable=True),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cached_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('audio_seconds', sa.Numeric(10, 3), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(12, 6), nullable=False, server_default='0'),
        sa.Column('pricing', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['presentation_session_id'], ['presentation_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'presentation_session_id',
            'operation',
            'source_id',
            name='uq_ai_usage_event_source',
        ),
    )
    op.create_index('ix_ai_usage_events_presentation_session_id', 'ai_usage_events', ['presentation_session_id'])
    op.create_index('ix_ai_usage_events_operation', 'ai_usage_events', ['operation'])
    op.create_index('ix_ai_usage_events_source_id', 'ai_usage_events', ['source_id'])
    op.create_index('ix_ai_usage_events_model', 'ai_usage_events', ['model'])


def downgrade() -> None:
    op.drop_index('ix_ai_usage_events_model', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_source_id', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_operation', table_name='ai_usage_events')
    op.drop_index('ix_ai_usage_events_presentation_session_id', table_name='ai_usage_events')
    op.drop_table('ai_usage_events')
