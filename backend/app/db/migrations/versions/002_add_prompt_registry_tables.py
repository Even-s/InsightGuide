"""add prompt_templates and prompt_versions tables

Revision ID: 002_add_prompt_registry
Revises: 001_add_brd_tables
Create Date: 2026-06-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_prompt_registry'
down_revision = '001_add_brd_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=False, server_default='medium'),
        sa.Column('service_file', sa.String(), nullable=True),
        sa.Column('service_function', sa.String(), nullable=True),
        sa.Column('input_variables', sa.JSON(), nullable=True),
        sa.Column('output_format', sa.String(), nullable=True),
        sa.Column('response_schema', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prompt_templates_key', 'prompt_templates', ['key'], unique=True)
    op.create_index('ix_prompt_templates_category', 'prompt_templates', ['category'])

    op.create_table(
        'prompt_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('user_prompt_template', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id']),
    )
    op.create_index('ix_prompt_versions_template_id', 'prompt_versions', ['template_id'])
    op.create_index('ix_prompt_versions_status', 'prompt_versions', ['status'])


def downgrade() -> None:
    op.drop_table('prompt_versions')
    op.drop_table('prompt_templates')
