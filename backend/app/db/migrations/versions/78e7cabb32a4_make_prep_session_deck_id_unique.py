"""make_prep_session_deck_id_unique

Revision ID: 78e7cabb32a4
Revises: e3ab8962e5b9
Create Date: 2026-05-26 11:56:25.180877

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '78e7cabb32a4'
down_revision = 'e3ab8962e5b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Delete duplicate prep_sessions, keeping only the most recent one per deck
    op.execute("""
        DELETE FROM prep_sessions
        WHERE id NOT IN (
            SELECT DISTINCT ON (deck_id) id
            FROM prep_sessions
            ORDER BY deck_id, created_at DESC
        )
    """)

    # Step 2: Update presentation_sessions to reference the new prep_session_id (deck_id)
    op.execute("""
        UPDATE presentation_sessions ps
        SET prep_session_id = (
            SELECT deck_id
            FROM prep_sessions prep
            WHERE prep.id = ps.prep_session_id
        )
        WHERE EXISTS (
            SELECT 1 FROM prep_sessions prep
            WHERE prep.id = ps.prep_session_id
        )
    """)

    # Step 3: Update prep_session IDs to match their deck_id
    op.execute("""
        UPDATE prep_sessions
        SET id = deck_id
        WHERE id != deck_id
    """)

    # Step 4: Add unique constraint to deck_id
    op.create_unique_constraint('uq_prep_sessions_deck_id', 'prep_sessions', ['deck_id'])


def downgrade() -> None:
    # Remove unique constraint
    op.drop_constraint('uq_prep_sessions_deck_id', 'prep_sessions', type_='unique')
