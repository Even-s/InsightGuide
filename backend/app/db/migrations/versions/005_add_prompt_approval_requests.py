"""add prompt_approval_requests table

Revision ID: 005_add_prompt_approvals
Revises: 004_add_prompt_ab_testing
Create Date: 2026-06-12 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '005_add_prompt_approvals'
down_revision = '004_add_prompt_ab_testing'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'prompt_approval_requests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('version_id', sa.String(), nullable=False),
        sa.Column('requester', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('reviewer', sa.String(), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id']),
        sa.ForeignKeyConstraint(['version_id'], ['prompt_versions.id']),
    )
    op.create_index('ix_prompt_approval_requests_template_id', 'prompt_approval_requests', ['template_id'])
    op.create_index('ix_prompt_approval_requests_status', 'prompt_approval_requests', ['status'])


def downgrade() -> None:
    op.drop_table('prompt_approval_requests')
