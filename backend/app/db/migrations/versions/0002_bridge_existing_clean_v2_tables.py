"""Bridge existing clean-v2 databases to the new multi-role tables.

Revision ID: 0002_bridge_existing_clean_v2
Revises: 0001_clean_v2_baseline
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "0002_bridge_existing_clean_v2"
down_revision: Union[str, None] = "0001_clean_v2_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {
        column["name"] for column in inspect(op.get_bind()).get_columns(table_name)
    }


def upgrade() -> None:
    if not _has_table("stakeholder_profile_slots"):
        op.create_table(
            "stakeholder_profile_slots",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("project_id", sa.String(), nullable=False),
            sa.Column("profile_id", sa.String(), nullable=False),
            sa.Column("slot_id", sa.String(), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("fit_level", sa.String(), nullable=False, server_default="primary"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["profile_id"], ["stakeholder_profiles.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["slot_id"], ["stakeholder_slots.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("profile_id", "slot_id", name="uq_stakeholder_profile_slot"),
        )
        op.create_index(
            op.f("ix_stakeholder_profile_slots_profile_id"),
            "stakeholder_profile_slots",
            ["profile_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_stakeholder_profile_slots_project_id"),
            "stakeholder_profile_slots",
            ["project_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_stakeholder_profile_slots_slot_id"),
            "stakeholder_profile_slots",
            ["slot_id"],
            unique=False,
        )

    if _has_column("stakeholder_profiles", "slot_id"):
        op.execute(
            sa.text(
                """
                INSERT INTO stakeholder_profile_slots (
                    id, project_id, profile_id, slot_id, is_primary, fit_level, created_at, updated_at
                )
                SELECT
                    'sps_' || substr(md5(id || ':' || slot_id), 1, 12),
                    project_id,
                    id,
                    slot_id,
                    true,
                    'primary',
                    now(),
                    now()
                FROM stakeholder_profiles
                WHERE slot_id IS NOT NULL
                ON CONFLICT (profile_id, slot_id) DO NOTHING
                """
            )
        )
        op.drop_index(op.f("ix_stakeholder_profiles_slot_id"), table_name="stakeholder_profiles")
        op.drop_column("stakeholder_profiles", "slot_id")

    if not _has_table("interview_round_slots"):
        op.create_table(
            "interview_round_slots",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("round_id", sa.String(), nullable=False),
            sa.Column("slot_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["round_id"], ["interview_rounds.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["slot_id"], ["stakeholder_slots.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("round_id", "slot_id", name="uq_interview_round_slot"),
        )
        op.create_index(
            op.f("ix_interview_round_slots_round_id"),
            "interview_round_slots",
            ["round_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_interview_round_slots_slot_id"),
            "interview_round_slots",
            ["slot_id"],
            unique=False,
        )

    if not _has_table("question_card_slots"):
        op.create_table(
            "question_card_slots",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("question_card_id", sa.String(), nullable=False),
            sa.Column("slot_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["question_card_id"], ["question_cards.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["slot_id"], ["stakeholder_slots.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("question_card_id", "slot_id", name="uq_question_card_slot"),
        )
        op.create_index(
            op.f("ix_question_card_slots_question_card_id"),
            "question_card_slots",
            ["question_card_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_question_card_slots_slot_id"),
            "question_card_slots",
            ["slot_id"],
            unique=False,
        )

    if not _has_table("card_evidence_slots"):
        op.create_table(
            "card_evidence_slots",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("evidence_id", sa.String(), nullable=False),
            sa.Column("slot_id", sa.String(), nullable=False),
            sa.Column("relevance", sa.Numeric(precision=4, scale=3), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["evidence_id"], ["card_criterion_evidence.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["slot_id"], ["stakeholder_slots.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("evidence_id", "slot_id", name="uq_card_evidence_slot"),
        )
        op.create_index(
            op.f("ix_card_evidence_slots_evidence_id"),
            "card_evidence_slots",
            ["evidence_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_card_evidence_slots_slot_id"),
            "card_evidence_slots",
            ["slot_id"],
            unique=False,
        )


def downgrade() -> None:
    if _has_table("card_evidence_slots"):
        op.drop_index(op.f("ix_card_evidence_slots_slot_id"), table_name="card_evidence_slots")
        op.drop_index(op.f("ix_card_evidence_slots_evidence_id"), table_name="card_evidence_slots")
        op.drop_table("card_evidence_slots")
    if _has_table("question_card_slots"):
        op.drop_index(op.f("ix_question_card_slots_slot_id"), table_name="question_card_slots")
        op.drop_index(
            op.f("ix_question_card_slots_question_card_id"), table_name="question_card_slots"
        )
        op.drop_table("question_card_slots")
    if _has_table("interview_round_slots"):
        op.drop_index(op.f("ix_interview_round_slots_slot_id"), table_name="interview_round_slots")
        op.drop_index(op.f("ix_interview_round_slots_round_id"), table_name="interview_round_slots")
        op.drop_table("interview_round_slots")
    if _has_table("stakeholder_profile_slots"):
        op.drop_index(
            op.f("ix_stakeholder_profile_slots_slot_id"),
            table_name="stakeholder_profile_slots",
        )
        op.drop_index(
            op.f("ix_stakeholder_profile_slots_project_id"),
            table_name="stakeholder_profile_slots",
        )
        op.drop_index(
            op.f("ix_stakeholder_profile_slots_profile_id"),
            table_name="stakeholder_profile_slots",
        )
        op.drop_table("stakeholder_profile_slots")
