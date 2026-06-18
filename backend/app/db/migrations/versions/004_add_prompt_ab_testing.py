"""add prompt A/B testing tables

Revision ID: 004_add_prompt_ab_testing
Revises: 003_add_prompt_audit_usage
Create Date: 2026-06-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '004_add_prompt_ab_testing'
down_revision = '003_add_prompt_audit_usage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'prompt_ab_tests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('variant_a_id', sa.String(), nullable=False),
        sa.Column('variant_b_id', sa.String(), nullable=False),
        sa.Column('traffic_percent_b', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('winner', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id']),
        sa.ForeignKeyConstraint(['variant_a_id'], ['prompt_versions.id']),
        sa.ForeignKeyConstraint(['variant_b_id'], ['prompt_versions.id']),
    )
    op.create_index('ix_prompt_ab_tests_template_id', 'prompt_ab_tests', ['template_id'])

    op.create_table(
        'prompt_ab_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('test_id', sa.String(), nullable=False),
        sa.Column('variant', sa.String(), nullable=False),
        sa.Column('version_id', sa.String(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='success'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['test_id'], ['prompt_ab_tests.id']),
        sa.ForeignKeyConstraint(['version_id'], ['prompt_versions.id']),
    )
    op.create_index('ix_prompt_ab_results_test_id', 'prompt_ab_results', ['test_id'])


def downgrade() -> None:
    op.drop_table('prompt_ab_results')
    op.drop_table('prompt_ab_tests')
