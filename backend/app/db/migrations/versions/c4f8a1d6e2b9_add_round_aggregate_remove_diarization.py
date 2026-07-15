"""Add round aggregates and permanently remove the retired diarization schema.

Revision ID: c4f8a1d6e2b9
Revises: a9c4e7b2d5f1

This migration intentionally deletes the obsolete diarization, alignment,
speaker Q/A reconstruction, and legacy transcript rows. Realtime transcript
segments in ``live_utterances`` remain untouched and become the sole source.
"""

import sqlalchemy as sa
from alembic import op

revision = "c4f8a1d6e2b9"
down_revision = "a9c4e7b2d5f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_round_aggregates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("round_id", sa.String(), nullable=False),
        sa.Column("latest_memo_id", sa.String(), nullable=True),
        sa.Column("source_session_ids", sa.JSON(), nullable=False),
        sa.Column("coverage_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["round_id"], ["interview_rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["latest_memo_id"], ["interview_insight_memos.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id", name="uq_interview_round_aggregates_round_id"),
        sa.UniqueConstraint("latest_memo_id", name="uq_interview_round_aggregates_latest_memo_id"),
    )
    op.create_index(
        "ix_interview_round_aggregates_round_id",
        "interview_round_aggregates",
        ["round_id"],
    )
    op.create_index(
        "ix_interview_round_aggregates_latest_memo_id",
        "interview_round_aggregates",
        ["latest_memo_id"],
    )
    op.create_index(
        "ix_interview_round_aggregates_status",
        "interview_round_aggregates",
        ["status"],
    )
    op.execute(
        """
        WITH ranked_memos AS (
            SELECT
                m.id,
                m.interview_round_id,
                ROW_NUMBER() OVER (
                    PARTITION BY m.interview_round_id
                    ORDER BY m.generated_at DESC NULLS LAST, m.created_at DESC, m.id DESC
                ) AS memo_rank
            FROM interview_insight_memos AS m
            WHERE m.status = 'completed' AND m.interview_round_id IS NOT NULL
        ), session_sources AS (
            SELECT
                s.interview_round_id,
                json_agg(s.id ORDER BY s.created_at, s.id) AS session_ids
            FROM interview_sessions AS s
            WHERE s.interview_round_id IS NOT NULL
            GROUP BY s.interview_round_id
        )
        INSERT INTO interview_round_aggregates (
            id,
            round_id,
            latest_memo_id,
            source_session_ids,
            coverage_snapshot,
            evidence_snapshot,
            status,
            version,
            generated_at,
            invalidated_at,
            created_at,
            updated_at
        )
        SELECT
            'roundagg_' || substr(md5(r.id || clock_timestamp()::text), 1, 12),
            r.id,
            m.id,
            COALESCE(ss.session_ids, '[]'::json),
            '{}'::json,
            '[]'::json,
            CASE WHEN m.id IS NULL THEN 'partial' ELSE 'ready' END,
            1,
            CASE WHEN m.id IS NULL THEN NULL ELSE NOW() END,
            NULL,
            NOW(),
            NOW()
        FROM interview_rounds AS r
        LEFT JOIN ranked_memos AS m
            ON m.interview_round_id = r.id AND m.memo_rank = 1
        LEFT JOIN session_sources AS ss ON ss.interview_round_id = r.id
        """
    )

    # Tables derived only from the retired diarization revisions.
    op.drop_table("question_answers")
    op.drop_table("question_instances")
    op.drop_table("utterance_alignment")

    op.execute(
        "ALTER TABLE interview_sessions "
        "DROP CONSTRAINT IF EXISTS fk_interview_sessions_final_transcript_revision_id"
    )
    op.drop_column("interview_sessions", "card_coverage_status")
    op.drop_column("interview_sessions", "final_transcript_revision_id")
    op.drop_column("interview_sessions", "transcript_status")

    op.drop_index(
        "ix_card_coverage_evaluations_session_card_basis",
        table_name="card_coverage_evaluations",
    )
    op.drop_index(
        "ix_card_coverage_evaluations_basis_type",
        table_name="card_coverage_evaluations",
    )
    op.execute(
        "ALTER TABLE card_coverage_evaluations "
        "DROP CONSTRAINT IF EXISTS card_coverage_evaluations_transcript_revision_id_fkey"
    )
    op.drop_column("card_coverage_evaluations", "transcript_revision_id")
    op.drop_column("card_coverage_evaluations", "basis_type")
    op.create_index(
        "ix_card_coverage_evaluations_session_card",
        "card_coverage_evaluations",
        ["session_id", "card_id"],
    )

    op.drop_table("final_utterances")
    op.drop_table("transcript_revisions")
    op.drop_table("utterances")


def downgrade() -> None:
    raise RuntimeError(
        "This migration permanently removes obsolete diarization data and cannot be downgraded."
    )
