"""Add utterance alignment table - Phase 5

Revision ID: 009_add_alignment
Revises: 008_add_qa_tables
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009_add_alignment'
down_revision = '008_add_qa_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create utterance_alignment table."""

    op.create_table(
        'utterance_alignment',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('live_utterance_id', sa.String(), nullable=True),
        sa.Column('final_utterance_id', sa.String(), nullable=True),
        sa.Column('transcript_revision_id', sa.String(), nullable=False),
        sa.Column('time_overlap_score', sa.Float(), nullable=True),
        sa.Column('text_similarity_score', sa.Float(), nullable=True),
        sa.Column('alignment_confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['live_utterance_id'], ['live_utterances.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['final_utterance_id'], ['final_utterances.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transcript_revision_id'], ['transcript_revisions.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('ix_alignment_session_id', 'utterance_alignment', ['session_id'])
    op.create_index('ix_alignment_live_id', 'utterance_alignment', ['live_utterance_id'])
    op.create_index('ix_alignment_final_id', 'utterance_alignment', ['final_utterance_id'])


def downgrade():
    """Drop utterance_alignment table."""
    op.drop_index('ix_alignment_final_id', table_name='utterance_alignment')
    op.drop_index('ix_alignment_live_id', table_name='utterance_alignment')
    op.drop_index('ix_alignment_session_id', table_name='utterance_alignment')
    op.drop_table('utterance_alignment')
