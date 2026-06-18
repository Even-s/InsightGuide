"""add transcript split tables

Revision ID: 006_add_transcript_split_tables
Revises: 005_add_prompt_approval_requests
Create Date: 2026-06-15

Phase 1: Data Flow Separation
- Creates live_utterances for Realtime API transcripts
- Creates transcript_revisions for version management
- Creates final_utterances for diarized transcripts
- Adds transcript management fields to interview_sessions
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_transcript_split_tables'
down_revision = '005_add_prompt_approvals'
branch_labels = None
depends_on = None


def upgrade():
    # Create live_utterances table
    op.create_table(
        'live_utterances',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('realtime_event_id', sa.String(), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('speaker', sa.String(), nullable=False, server_default='unknown'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('sequence_index', sa.Integer(), nullable=False),
        sa.Column('is_partial', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_live_utterances_session_id', 'live_utterances', ['session_id'])

    # Create transcript_revisions table
    op.create_table(
        'transcript_revisions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('recording_started_at', sa.DateTime(), nullable=True),
        sa.Column('audio_file_url', sa.Text(), nullable=True),
        sa.Column('segment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_transcript_revisions_session_id', 'transcript_revisions', ['session_id'])

    # Create final_utterances table
    op.create_table(
        'final_utterances',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('transcript_revision_id', sa.String(), nullable=False),
        sa.Column('speaker_label', sa.String(), nullable=False),
        sa.Column('speaker_role', sa.String(), nullable=True),
        sa.Column('speaker_display_name', sa.String(), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('start_seconds', sa.Float(), nullable=True),
        sa.Column('end_seconds', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('sequence_index', sa.Integer(), nullable=False),
        sa.Column('theme_id', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transcript_revision_id'], ['transcript_revisions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_final_utterances_session_id', 'final_utterances', ['session_id'])
    op.create_index('ix_final_utterances_transcript_revision_id', 'final_utterances', ['transcript_revision_id'])

    # Add new columns to interview_sessions
    op.add_column('interview_sessions', sa.Column('transcript_status', sa.String(), nullable=False, server_default='live_only'))
    op.add_column('interview_sessions', sa.Column('final_transcript_revision_id', sa.String(), nullable=True))
    op.add_column('interview_sessions', sa.Column('card_coverage_status', sa.String(), nullable=False, server_default='provisional'))

    # Add foreign key constraint for final_transcript_revision_id
    op.create_foreign_key(
        'fk_interview_sessions_final_transcript_revision_id',
        'interview_sessions',
        'transcript_revisions',
        ['final_transcript_revision_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    # Drop foreign key constraint
    op.drop_constraint('fk_interview_sessions_final_transcript_revision_id', 'interview_sessions', type_='foreignkey')

    # Drop new columns from interview_sessions
    op.drop_column('interview_sessions', 'card_coverage_status')
    op.drop_column('interview_sessions', 'final_transcript_revision_id')
    op.drop_column('interview_sessions', 'transcript_status')

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_index('ix_final_utterances_transcript_revision_id', 'final_utterances')
    op.drop_index('ix_final_utterances_session_id', 'final_utterances')
    op.drop_table('final_utterances')

    op.drop_index('ix_transcript_revisions_session_id', 'transcript_revisions')
    op.drop_table('transcript_revisions')

    op.drop_index('ix_live_utterances_session_id', 'live_utterances')
    op.drop_table('live_utterances')
