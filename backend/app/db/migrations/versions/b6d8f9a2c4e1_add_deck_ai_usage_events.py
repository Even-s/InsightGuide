"""add_deck_ai_usage_events

Revision ID: b6d8f9a2c4e1
Revises: 9a7f2b4d1c3e
Create Date: 2026-06-04 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b6d8f9a2c4e1'
down_revision = '9a7f2b4d1c3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ai_usage_events', sa.Column('deck_id', sa.String(), nullable=True))
    op.alter_column('ai_usage_events', 'presentation_session_id', nullable=True)
    op.create_foreign_key(
        'fk_ai_usage_events_deck_id_decks',
        'ai_usage_events',
        'decks',
        ['deck_id'],
        ['id'],
    )
    op.create_index('ix_ai_usage_events_deck_id', 'ai_usage_events', ['deck_id'])
    op.create_unique_constraint(
        'uq_ai_usage_event_deck_source',
        'ai_usage_events',
        ['deck_id', 'operation', 'source_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_ai_usage_event_deck_source', 'ai_usage_events', type_='unique')
    op.drop_index('ix_ai_usage_events_deck_id', table_name='ai_usage_events')
    op.drop_constraint('fk_ai_usage_events_deck_id_decks', 'ai_usage_events', type_='foreignkey')
    op.alter_column('ai_usage_events', 'presentation_session_id', nullable=False)
    op.drop_column('ai_usage_events', 'deck_id')
