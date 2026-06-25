"""Add card_criterion_evidence table.

Revision ID: a1b2c3d4e5f6
"""
import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "015_add_readiness_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_criterion_evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("card_id", sa.String(), nullable=False),
        sa.Column("criterion_id", sa.String(), nullable=False),
        sa.Column("utterance_id", sa.String(), nullable=True),
        sa.Column("evaluation_turn_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("evaluator_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("evaluation_seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["question_cards.id"]),
        sa.ForeignKeyConstraint(["utterance_id"], ["live_utterances.id"]),
    )
    op.create_index("ix_card_criterion_evidence_session_id", "card_criterion_evidence", ["session_id"])
    op.create_index("ix_card_criterion_evidence_card_id", "card_criterion_evidence", ["card_id"])
    op.create_index("ix_card_criterion_evidence_criterion_id", "card_criterion_evidence", ["criterion_id"])
    op.create_index("ix_cce_session_card", "card_criterion_evidence", ["session_id", "card_id"])
    op.create_index("ix_cce_session_card_criterion", "card_criterion_evidence", ["session_id", "card_id", "criterion_id"])


def downgrade() -> None:
    op.drop_table("card_criterion_evidence")
