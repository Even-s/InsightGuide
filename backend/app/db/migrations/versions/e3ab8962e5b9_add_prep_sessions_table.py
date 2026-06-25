"""add_prep_sessions_table

Revision ID: e3ab8962e5b9
Revises: 0edc97eda1b4
Create Date: 2026-05-26 10:44:29.427499

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e3ab8962e5b9'
down_revision = '0edc97eda1b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prep_sessions table
    op.create_table('prep_sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('deck_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['deck_id'], ['decks.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prep_sessions_deck_id'), 'prep_sessions', ['deck_id'], unique=False)
    op.create_index(op.f('ix_prep_sessions_status'), 'prep_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_prep_sessions_user_id'), 'prep_sessions', ['user_id'], unique=False)

    # Add prep_session_id column as nullable first (to handle existing data)
    op.add_column('presentation_sessions', sa.Column('prep_session_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_presentation_sessions_prep_session_id'), 'presentation_sessions', ['prep_session_id'], unique=False)

    # Data migration: Create one PrepSession per Deck and link existing PresentationSessions
    import uuid
    from datetime import datetime

    from sqlalchemy import DateTime, String
    from sqlalchemy.sql import column, table

    conn = op.get_bind()

    # Get all decks
    decks_table = table('decks',
        column('id', String),
        column('user_id', String)
    )
    decks = conn.execute(sa.select(decks_table.c.id, decks_table.c.user_id)).fetchall()

    # Create one prep session per deck
    prep_sessions_table = table('prep_sessions',
        column('id', String),
        column('deck_id', String),
        column('user_id', String),
        column('title', String),
        column('status', String),
        column('created_at', DateTime),
        column('updated_at', DateTime)
    )

    deck_to_prep_session = {}
    now = datetime.utcnow()

    for deck in decks:
        prep_session_id = f"prep_{uuid.uuid4().hex[:12]}"
        deck_to_prep_session[deck.id] = prep_session_id

        conn.execute(
            prep_sessions_table.insert().values(
                id=prep_session_id,
                deck_id=deck.id,
                user_id=deck.user_id,
                title=None,
                status='ready',
                created_at=now,
                updated_at=now
            )
        )

    # Link existing presentation sessions to prep sessions
    presentation_sessions_table = table('presentation_sessions',
        column('id', String),
        column('deck_id', String),
        column('prep_session_id', String)
    )

    sessions = conn.execute(
        sa.select(presentation_sessions_table.c.id, presentation_sessions_table.c.deck_id)
    ).fetchall()

    for session in sessions:
        prep_session_id = deck_to_prep_session.get(session.deck_id)
        if prep_session_id:
            conn.execute(
                presentation_sessions_table.update()
                .where(presentation_sessions_table.c.id == session.id)
                .values(prep_session_id=prep_session_id)
            )

    # Now make prep_session_id NOT NULL
    op.alter_column('presentation_sessions', 'prep_session_id', nullable=False)

    # Add foreign key constraint
    op.create_foreign_key('fk_presentation_sessions_prep_session_id', 'presentation_sessions', 'prep_sessions', ['prep_session_id'], ['id'])


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint('fk_presentation_sessions_prep_session_id', 'presentation_sessions', type_='foreignkey')
    op.drop_index(op.f('ix_presentation_sessions_prep_session_id'), table_name='presentation_sessions')
    op.drop_column('presentation_sessions', 'prep_session_id')

    # Drop prep_sessions table
    op.drop_index(op.f('ix_prep_sessions_user_id'), table_name='prep_sessions')
    op.drop_index(op.f('ix_prep_sessions_status'), table_name='prep_sessions')
    op.drop_index(op.f('ix_prep_sessions_deck_id'), table_name='prep_sessions')
    op.drop_table('prep_sessions')
