"""Add card_coverage_evaluations table - Phase 2

Revision ID: 007_add_card_coverage_evaluations
Revises: 006_add_transcript_split_tables
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_card_coverage_evals'
down_revision = '006_add_transcript_split_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create card_coverage_evaluations table."""
    op.create_table(
        'card_coverage_evaluations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('card_id', sa.String(), nullable=False),
        sa.Column('basis_type', sa.String(), nullable=False),
        sa.Column('transcript_revision_id', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('covered_element_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('missing_element_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('evaluation_seq', sa.Integer(), nullable=False),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['question_cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transcript_revision_id'], ['transcript_revisions.id'], ondelete='SET NULL'),
    )

    # Create indexes for common queries
    op.create_index('ix_card_coverage_evaluations_session_id', 'card_coverage_evaluations', ['session_id'])
    op.create_index('ix_card_coverage_evaluations_card_id', 'card_coverage_evaluations', ['card_id'])
    op.create_index('ix_card_coverage_evaluations_basis_type', 'card_coverage_evaluations', ['basis_type'])
    op.create_index(
        'ix_card_coverage_evaluations_session_card_basis',
        'card_coverage_evaluations',
        ['session_id', 'card_id', 'basis_type']
    )


def downgrade():
    """Drop card_coverage_evaluations table."""
    op.drop_index('ix_card_coverage_evaluations_session_card_basis', table_name='card_coverage_evaluations')
    op.drop_index('ix_card_coverage_evaluations_basis_type', table_name='card_coverage_evaluations')
    op.drop_index('ix_card_coverage_evaluations_card_id', table_name='card_coverage_evaluations')
    op.drop_index('ix_card_coverage_evaluations_session_id', table_name='card_coverage_evaluations')
    op.drop_table('card_coverage_evaluations')
