"""add brd and requirement tables

Revision ID: 001_add_brd_tables
Revises: f4c2a1b8d9e0
Create Date: 2026-06-10 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_brd_tables'
down_revision = 'b6d8f9a2c4e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create brd_drafts table
    op.create_table(
        'brd_drafts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('interview_session_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('GENERATING', 'COMPLETED', 'FAILED', 'EXPORTED', name='brdstatus'), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('executive_summary', sa.Text(), nullable=True),
        sa.Column('project_overview', sa.Text(), nullable=True),
        sa.Column('business_objectives', sa.JSON(), nullable=True),
        sa.Column('success_criteria', sa.JSON(), nullable=True),
        sa.Column('stakeholders', sa.JSON(), nullable=True),
        sa.Column('assumptions', sa.JSON(), nullable=True),
        sa.Column('constraints', sa.JSON(), nullable=True),
        sa.Column('risks', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('generation_duration_seconds', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('markdown_content', sa.Text(), nullable=True),
        sa.Column('last_exported_at', sa.DateTime(), nullable=True),
        sa.Column('export_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['interview_session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_brd_drafts_interview_session_id'), 'brd_drafts', ['interview_session_id'], unique=True)
    op.create_index(op.f('ix_brd_drafts_user_id'), 'brd_drafts', ['user_id'], unique=False)
    op.create_index(op.f('ix_brd_drafts_status'), 'brd_drafts', ['status'], unique=False)

    # Create requirements table
    op.create_table(
        'requirements',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('brd_draft_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('type', sa.Enum('FUNCTIONAL', 'NON_FUNCTIONAL', 'BUSINESS', 'USER', 'TECHNICAL', name='requirementtype'), nullable=False),
        sa.Column('priority', sa.Enum('MUST_HAVE', 'SHOULD_HAVE', 'NICE_TO_HAVE', name='requirementpriority'), nullable=False),
        sa.Column('source_question_card_id', sa.String(), nullable=True),
        sa.Column('source_utterance_ids', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.String(), nullable=True),
        sa.Column('user_story', sa.Text(), nullable=True),
        sa.Column('acceptance_criteria', sa.JSON(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['brd_draft_id'], ['brd_drafts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_question_card_id'], ['question_cards.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requirements_brd_draft_id'), 'requirements', ['brd_draft_id'], unique=False)
    op.create_index(op.f('ix_requirements_type'), 'requirements', ['type'], unique=False)
    op.create_index(op.f('ix_requirements_priority'), 'requirements', ['priority'], unique=False)
    op.create_index(op.f('ix_requirements_source_question_card_id'), 'requirements', ['source_question_card_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_requirements_source_question_card_id'), table_name='requirements')
    op.drop_index(op.f('ix_requirements_priority'), table_name='requirements')
    op.drop_index(op.f('ix_requirements_type'), table_name='requirements')
    op.drop_index(op.f('ix_requirements_brd_draft_id'), table_name='requirements')
    op.drop_table('requirements')
    op.execute('DROP TYPE requirementpriority')
    op.execute('DROP TYPE requirementtype')

    op.drop_index(op.f('ix_brd_drafts_status'), table_name='brd_drafts')
    op.drop_index(op.f('ix_brd_drafts_user_id'), table_name='brd_drafts')
    op.drop_index(op.f('ix_brd_drafts_interview_session_id'), table_name='brd_drafts')
    op.drop_table('brd_drafts')
    op.execute('DROP TYPE brdstatus')
