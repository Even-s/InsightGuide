"""add brd readiness reports table

Revision ID: 015_add_readiness_reports
Revises: 014_add_evidence_matrix
Create Date: 2026-06-16

Phase 5: BRD Readiness Report
- Creates brd_readiness_reports table (gatekeeper before BRD generation)
"""

import sqlalchemy as sa
from alembic import op

revision = '015_add_readiness_reports'
down_revision = '014_add_evidence_matrix'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'brd_readiness_reports',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('is_ready', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('readiness_score', sa.Float(), nullable=True),
        sa.Column('generation_mode', sa.String(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('ready_sections', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('insufficient_sections', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('unresolved_conflicts', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('suggested_next_interviews', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('stakeholder_coverage', sa.JSON(), nullable=True),
        sa.Column('total_memos', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_stakeholders_interviewed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_evidence_entries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('validated_requirements', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('markdown_content', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_brd_readiness_reports_project_id', 'brd_readiness_reports', ['project_id'])


def downgrade():
    op.drop_index('ix_brd_readiness_reports_project_id', 'brd_readiness_reports')
    op.drop_table('brd_readiness_reports')
