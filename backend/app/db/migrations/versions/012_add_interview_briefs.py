"""add interview briefs table

Revision ID: 012_add_interview_briefs
Revises: 011_add_card_role_targeting
Create Date: 2026-06-16

Phase 2: Interview Brief
- Creates interview_briefs table for role-based interview plans
"""

from alembic import op
import sqlalchemy as sa


revision = '012_add_interview_briefs'
down_revision = '011_add_card_role_targeting'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'interview_briefs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('stakeholder_profile_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('interview_objective', sa.Text(), nullable=False),
        sa.Column('recommended_topics', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('excluded_topics', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('suggested_questions', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('follow_up_from_prior_interviews', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('applicable_card_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('not_applicable_cards', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('time_estimate_minutes', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stakeholder_profile_id'], ['stakeholder_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('session_id'),
    )
    op.create_index('ix_interview_briefs_session_id', 'interview_briefs', ['session_id'])
    op.create_index('ix_interview_briefs_project_id', 'interview_briefs', ['project_id'])


def downgrade():
    op.drop_index('ix_interview_briefs_project_id', 'interview_briefs')
    op.drop_index('ix_interview_briefs_session_id', 'interview_briefs')
    op.drop_table('interview_briefs')
