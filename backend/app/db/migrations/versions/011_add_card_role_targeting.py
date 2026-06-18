"""add card role targeting columns

Revision ID: 011_add_card_role_targeting
Revises: 010_add_project_stakeholder_plan
Create Date: 2026-06-16

Phase 1: Card Role Targeting
- Adds target_roles, not_recommended_roles, expertise_required, question_intent to question_cards
- Enables role-aware card filtering during interviews
"""

from alembic import op
import sqlalchemy as sa


revision = '011_add_card_role_targeting'
down_revision = '010_add_project_stakeholder_plan'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('question_cards', sa.Column('target_roles', sa.JSON(), nullable=True))
    op.add_column('question_cards', sa.Column('not_recommended_roles', sa.JSON(), nullable=True))
    op.add_column('question_cards', sa.Column('expertise_required', sa.JSON(), nullable=True))
    op.add_column('question_cards', sa.Column('question_intent', sa.String(), nullable=True))


def downgrade():
    op.drop_column('question_cards', 'question_intent')
    op.drop_column('question_cards', 'expertise_required')
    op.drop_column('question_cards', 'not_recommended_roles')
    op.drop_column('question_cards', 'target_roles')
