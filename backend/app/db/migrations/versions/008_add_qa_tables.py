"""Add Q/A reconstruction tables - Phase 4

Revision ID: 008_add_qa_tables
Revises: 007_card_coverage_evals
Create Date: 2026-06-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008_add_qa_tables'
down_revision = '007_card_coverage_evals'
branch_labels = None
depends_on = None


def upgrade():
    """Create question_instances and question_answers tables."""

    # Create question_instances table
    op.create_table(
        'question_instances',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('source_question_id', sa.String(), nullable=True),
        sa.Column('theme_id', sa.String(), nullable=True),
        sa.Column('card_id', sa.String(), nullable=True),
        sa.Column('interviewer_utterance_id', sa.String(), nullable=True),
        sa.Column('asked_text', sa.Text(), nullable=False),
        sa.Column('normalized_question', sa.Text(), nullable=True),
        sa.Column('question_type', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('sequence_index', sa.Integer(), nullable=True),
        sa.Column('match_confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['question_cards.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['interviewer_utterance_id'], ['final_utterances.id'], ondelete='SET NULL'),
    )

    # Create indexes for question_instances
    op.create_index('ix_question_instances_session_id', 'question_instances', ['session_id'])
    op.create_index('ix_question_instances_card_id', 'question_instances', ['card_id'])

    # Create question_answers table
    op.create_table(
        'question_answers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('question_instance_id', sa.String(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('answer_summary', sa.Text(), nullable=True),
        sa.Column('answer_utterance_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence_quotes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('answer_status', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_instance_id'], ['question_instances.id'], ondelete='CASCADE'),
    )

    # Create indexes for question_answers
    op.create_index('ix_question_answers_session_id', 'question_answers', ['session_id'])
    op.create_index('ix_question_answers_question_instance_id', 'question_answers', ['question_instance_id'])


def downgrade():
    """Drop Q/A reconstruction tables."""
    # Drop question_answers first (has FK to question_instances)
    op.drop_index('ix_question_answers_question_instance_id', table_name='question_answers')
    op.drop_index('ix_question_answers_session_id', table_name='question_answers')
    op.drop_table('question_answers')

    # Drop question_instances
    op.drop_index('ix_question_instances_card_id', table_name='question_instances')
    op.drop_index('ix_question_instances_session_id', table_name='question_instances')
    op.drop_table('question_instances')
