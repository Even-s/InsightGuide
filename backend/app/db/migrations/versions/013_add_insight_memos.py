"""add interview insight memos table

Revision ID: 013_add_insight_memos
Revises: 012_add_interview_briefs
Create Date: 2026-06-16

Phase 3: Interview Insight Memo
- Creates interview_insight_memos table for structured post-interview insights
"""

import sqlalchemy as sa
from alembic import op

revision = '013_add_insight_memos'
down_revision = '012_add_interview_briefs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'interview_insight_memos',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('stakeholder_profile_id', sa.String(), nullable=True),
        sa.Column('interview_date', sa.DateTime(), nullable=True),
        sa.Column('interview_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('topics_covered', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('stakeholder_summary', sa.JSON(), nullable=True),
        sa.Column('qa_summaries', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('pain_points', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('requirement_candidates', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('constraints_and_assumptions', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('process_descriptions', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('unresolved_questions', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('next_interview_suggestions', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('source_distinction', sa.JSON(), nullable=True),
        sa.Column('markdown_content', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='generating'),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['stakeholder_profile_id'], ['stakeholder_profiles.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('session_id'),
    )
    op.create_index('ix_insight_memos_session_id', 'interview_insight_memos', ['session_id'])
    op.create_index('ix_insight_memos_project_id', 'interview_insight_memos', ['project_id'])
    op.create_index('ix_insight_memos_stakeholder_id', 'interview_insight_memos', ['stakeholder_profile_id'])


def downgrade():
    op.drop_index('ix_insight_memos_stakeholder_id', 'interview_insight_memos')
    op.drop_index('ix_insight_memos_project_id', 'interview_insight_memos')
    op.drop_index('ix_insight_memos_session_id', 'interview_insight_memos')
    op.drop_table('interview_insight_memos')
