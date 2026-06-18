"""add evidence matrix tables

Revision ID: 014_add_evidence_matrix
Revises: 013_add_insight_memos
Create Date: 2026-06-16

Phase 4: Requirement Evidence Matrix
- Creates requirement_evidence_matrices table (one per project)
- Creates evidence_matrix_entries table (individual candidate requirements)
"""

from alembic import op
import sqlalchemy as sa


revision = '014_add_evidence_matrix'
down_revision = '013_add_insight_memos'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'requirement_evidence_matrices',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('last_updated_at', sa.DateTime(), nullable=True),
        sa.Column('memo_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_memo_id', sa.String(), nullable=True),
        sa.Column('markdown_content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('project_id'),
    )
    op.create_index('ix_evidence_matrices_project_id', 'requirement_evidence_matrices', ['project_id'])

    op.create_table(
        'evidence_matrix_entries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('matrix_id', sa.String(), nullable=False),
        sa.Column('requirement_candidate', sa.Text(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('source_roles', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('source_memo_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('supporting_evidence', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('conflicts', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('validation_status', sa.String(), nullable=False, server_default='candidate'),
        sa.Column('missing_validation_from', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('mention_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('stakeholder_agreement_level', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['matrix_id'], ['requirement_evidence_matrices.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_evidence_matrix_entries_matrix_id', 'evidence_matrix_entries', ['matrix_id'])


def downgrade():
    op.drop_index('ix_evidence_matrix_entries_matrix_id', 'evidence_matrix_entries')
    op.drop_table('evidence_matrix_entries')
    op.drop_index('ix_evidence_matrices_project_id', 'requirement_evidence_matrices')
    op.drop_table('requirement_evidence_matrices')
