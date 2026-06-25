"""add project and stakeholder plan tables

Revision ID: 010_add_project_stakeholder_plan
Revises: 009_add_alignment
Create Date: 2026-06-16

Phase 0: Project + Stakeholder Plan + Stakeholder Profile
- Creates projects table (top-level BRD initiative container)
- Creates stakeholder_slots table (AI-suggested role slots)
- Creates stakeholder_profiles table (actual interviewees)
- Adds project_id and stakeholder_profile_id to interview_sessions
- Adds project_id to documents
"""

import sqlalchemy as sa
from alembic import op

revision = '010_add_project_stakeholder_plan'
down_revision = '009_add_alignment'
branch_labels = None
depends_on = None


def upgrade():
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('brd_scope', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'])
    op.create_index('ix_projects_status', 'projects', ['status'])

    # Create stakeholder_slots table
    op.create_table(
        'stakeholder_slots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('role_category', sa.String(), nullable=False),
        sa.Column('role_label', sa.String(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('expected_contributions', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('key_questions_to_cover', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('priority', sa.String(), nullable=False, server_default='required'),
        sa.Column('min_interviews', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(), nullable=False, server_default='unassigned'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source', sa.String(), nullable=False, server_default='ai_suggested'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_stakeholder_slots_project_id', 'stakeholder_slots', ['project_id'])

    # Create stakeholder_profiles table
    op.create_table(
        'stakeholder_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('slot_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role_title', sa.String(), nullable=True),
        sa.Column('department', sa.String(), nullable=True),
        sa.Column('stakeholder_type', sa.String(), nullable=False),
        sa.Column('expertise_tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('knowledge_boundaries', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('decision_power', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='scheduled'),
        sa.Column('interview_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_interviewed_at', sa.DateTime(), nullable=True),
        sa.Column('recommended_by_memo_id', sa.String(), nullable=True),
        sa.Column('recommended_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_id'], ['stakeholder_slots.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_stakeholder_profiles_project_id', 'stakeholder_profiles', ['project_id'])
    op.create_index('ix_stakeholder_profiles_slot_id', 'stakeholder_profiles', ['slot_id'])

    # Add project_id to documents
    op.add_column('documents', sa.Column('project_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'fk_documents_project_id', 'documents', 'projects',
        ['project_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_documents_project_id', 'documents', ['project_id'])

    # Add project_id and stakeholder_profile_id to interview_sessions
    op.add_column('interview_sessions', sa.Column('project_id', sa.String(), nullable=True))
    op.add_column('interview_sessions', sa.Column('stakeholder_profile_id', sa.String(), nullable=True))
    op.add_column('interview_sessions', sa.Column('interview_objective', sa.Text(), nullable=True))
    op.add_column('interview_sessions', sa.Column('interview_scope', sa.JSON(), nullable=True))
    op.create_foreign_key(
        'fk_interview_sessions_project_id', 'interview_sessions', 'projects',
        ['project_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_interview_sessions_stakeholder_profile_id', 'interview_sessions', 'stakeholder_profiles',
        ['stakeholder_profile_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_interview_sessions_project_id', 'interview_sessions', ['project_id'])
    op.create_index('ix_interview_sessions_stakeholder_profile_id', 'interview_sessions', ['stakeholder_profile_id'])


def downgrade():
    op.drop_index('ix_interview_sessions_stakeholder_profile_id', 'interview_sessions')
    op.drop_index('ix_interview_sessions_project_id', 'interview_sessions')
    op.drop_constraint('fk_interview_sessions_stakeholder_profile_id', 'interview_sessions', type_='foreignkey')
    op.drop_constraint('fk_interview_sessions_project_id', 'interview_sessions', type_='foreignkey')
    op.drop_column('interview_sessions', 'interview_scope')
    op.drop_column('interview_sessions', 'interview_objective')
    op.drop_column('interview_sessions', 'stakeholder_profile_id')
    op.drop_column('interview_sessions', 'project_id')

    op.drop_index('ix_documents_project_id', 'documents')
    op.drop_constraint('fk_documents_project_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'project_id')

    op.drop_index('ix_stakeholder_profiles_slot_id', 'stakeholder_profiles')
    op.drop_index('ix_stakeholder_profiles_project_id', 'stakeholder_profiles')
    op.drop_table('stakeholder_profiles')

    op.drop_index('ix_stakeholder_slots_project_id', 'stakeholder_slots')
    op.drop_table('stakeholder_slots')

    op.drop_index('ix_projects_status', 'projects')
    op.drop_index('ix_projects_user_id', 'projects')
    op.drop_table('projects')
