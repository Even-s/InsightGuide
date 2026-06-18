"""add prompt_audit_logs and prompt_usage_logs tables

Revision ID: 003_add_prompt_audit_usage
Revises: 002_add_prompt_registry
Create Date: 2026-06-12 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '003_add_prompt_audit_usage'
down_revision = '002_add_prompt_registry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'prompt_audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('version_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('actor', sa.String(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id']),
        sa.ForeignKeyConstraint(['version_id'], ['prompt_versions.id']),
    )
    op.create_index('ix_prompt_audit_logs_template_id', 'prompt_audit_logs', ['template_id'])

    op.create_table(
        'prompt_usage_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_key', sa.String(), nullable=False),
        sa.Column('version_id', sa.String(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prompt_usage_logs_template_key', 'prompt_usage_logs', ['template_key'])


def downgrade() -> None:
    op.drop_table('prompt_usage_logs')
    op.drop_table('prompt_audit_logs')
