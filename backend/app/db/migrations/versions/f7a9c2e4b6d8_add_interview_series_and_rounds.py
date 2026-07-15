"""Add interview series and immutable interview rounds.

Revision ID: f7a9c2e4b6d8
Revises: e6a1c4d8f2b9
"""

import sqlalchemy as sa
from alembic import op

revision = "f7a9c2e4b6d8"
down_revision = "e6a1c4d8f2b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_series",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("stakeholder_profile_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("topic_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["stakeholder_profile_id"], ["stakeholder_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "stakeholder_profile_id",
            "topic_key",
            name="uq_interview_series_project_profile_topic",
        ),
    )
    op.create_index("ix_interview_series_project_id", "interview_series", ["project_id"])
    op.create_index(
        "ix_interview_series_stakeholder_profile_id",
        "interview_series",
        ["stakeholder_profile_id"],
    )
    op.create_index("ix_interview_series_status", "interview_series", ["status"])

    op.create_table(
        "interview_rounds",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("series_id", sa.String(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("generation_mode", sa.String(), nullable=False, server_default="follow_up"),
        sa.Column("source_session_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("focus_topics", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "exclude_completed_questions", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("guide_document_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["series_id"], ["interview_series.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guide_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_id", "round_number", name="uq_interview_round_series_number"),
    )
    op.create_index("ix_interview_rounds_series_id", "interview_rounds", ["series_id"])
    op.create_index(
        "ix_interview_rounds_guide_document_id", "interview_rounds", ["guide_document_id"]
    )
    op.create_index("ix_interview_rounds_status", "interview_rounds", ["status"])

    op.add_column("documents", sa.Column("interview_round_id", sa.String(), nullable=True))
    op.add_column(
        "documents", sa.Column("guide_version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "documents", sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.create_foreign_key(
        "fk_documents_interview_round_id",
        "documents",
        "interview_rounds",
        ["interview_round_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_interview_round_id", "documents", ["interview_round_id"])
    op.create_index("ix_documents_is_frozen", "documents", ["is_frozen"])

    op.add_column("interview_sessions", sa.Column("interview_round_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_interview_sessions_interview_round_id",
        "interview_sessions",
        "interview_rounds",
        ["interview_round_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_interview_sessions_interview_round_id",
        "interview_sessions",
        ["interview_round_id"],
    )
    op.create_unique_constraint(
        "uq_interview_sessions_interview_round_id",
        "interview_sessions",
        ["interview_round_id"],
    )

    op.add_column(
        "interview_insight_memos", sa.Column("interview_series_id", sa.String(), nullable=True)
    )
    op.add_column(
        "interview_insight_memos", sa.Column("interview_round_id", sa.String(), nullable=True)
    )
    op.create_foreign_key(
        "fk_insight_memos_interview_series_id",
        "interview_insight_memos",
        "interview_series",
        ["interview_series_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_insight_memos_interview_round_id",
        "interview_insight_memos",
        "interview_rounds",
        ["interview_round_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_interview_insight_memos_interview_series_id",
        "interview_insight_memos",
        ["interview_series_id"],
    )
    op.create_index(
        "ix_interview_insight_memos_interview_round_id",
        "interview_insight_memos",
        ["interview_round_id"],
    )

    _backfill_existing_interviews()


def _backfill_existing_interviews() -> None:
    # Create one default topic series for every existing generated guide or linked session.
    op.execute(
        """
        INSERT INTO interview_series (
            id, project_id, stakeholder_profile_id, title, topic_key, status, created_at, updated_at
        )
        SELECT
            'series_' || substr(md5(base.project_id || ':' || base.stakeholder_profile_id), 1, 12),
            base.project_id,
            base.stakeholder_profile_id,
            COALESCE(slot.role_label, '既有訪談主題'),
            'default',
            'active',
            NOW(),
            NOW()
        FROM (
            SELECT DISTINCT project_id, stakeholder_profile_id
            FROM documents
            WHERE project_id IS NOT NULL AND stakeholder_profile_id IS NOT NULL
            UNION
            SELECT DISTINCT project_id, stakeholder_profile_id
            FROM interview_sessions
            WHERE project_id IS NOT NULL AND stakeholder_profile_id IS NOT NULL
        ) base
        LEFT JOIN stakeholder_profiles profile ON profile.id = base.stakeholder_profile_id
        LEFT JOIN stakeholder_slots slot ON slot.id = profile.slot_id
        ON CONFLICT (project_id, stakeholder_profile_id, topic_key) DO NOTHING
        """
    )

    # Every historical session becomes a separate round, while sharing its legacy guide read-only.
    op.execute(
        """
        INSERT INTO interview_rounds (
            id, series_id, round_number, objective, generation_mode,
            source_session_ids, focus_topics, exclude_completed_questions,
            guide_document_id, status, created_at, updated_at
        )
        SELECT
            'round_' || substr(md5(ranked.id), 1, 12),
            ranked.series_id,
            ranked.round_number,
            ranked.interview_objective,
            'legacy',
            json_build_array(ranked.id),
            '[]'::json,
            TRUE,
            ranked.document_id,
            CASE
                WHEN ranked.status = 'ended' THEN 'completed'
                WHEN ranked.status IN ('interviewing', 'paused') THEN 'interviewing'
                ELSE 'guide_ready'
            END,
            ranked.created_at,
            ranked.created_at
        FROM (
            SELECT
                session.*,
                series.id AS series_id,
                row_number() OVER (
                    PARTITION BY series.id ORDER BY session.created_at, session.id
                ) AS round_number
            FROM interview_sessions session
            JOIN interview_series series
              ON series.project_id = session.project_id
             AND series.stakeholder_profile_id = session.stakeholder_profile_id
             AND series.topic_key = 'default'
        ) ranked
        ON CONFLICT (series_id, round_number) DO NOTHING
        """
    )

    op.execute(
        """
        UPDATE interview_sessions session
        SET interview_round_id = round.id
        FROM interview_rounds round,
             json_array_elements_text(round.source_session_ids) source_session_id
        WHERE session.interview_round_id IS NULL
          AND round.generation_mode = 'legacy'
          AND source_session_id = session.id
        """
    )

    # Draft guides without sessions get their own next round.
    op.execute(
        """
        INSERT INTO interview_rounds (
            id, series_id, round_number, objective, generation_mode,
            source_session_ids, focus_topics, exclude_completed_questions,
            guide_document_id, status, created_at, updated_at
        )
        SELECT
            'round_' || substr(md5(document.id || '-draft'), 1, 12),
            series.id,
            (COALESCE(existing.max_round, 0) + row_number() OVER (
                PARTITION BY series.id ORDER BY document.created_at, document.id
            ))::integer,
            document.interview_objective,
            'legacy',
            '[]'::json,
            '[]'::json,
            TRUE,
            document.id,
            'guide_ready',
            document.created_at,
            document.updated_at
        FROM documents document
        JOIN interview_series series
          ON series.project_id = document.project_id
         AND series.stakeholder_profile_id = document.stakeholder_profile_id
         AND series.topic_key = 'default'
        LEFT JOIN (
            SELECT series_id, max(round_number) AS max_round
            FROM interview_rounds
            GROUP BY series_id
        ) existing ON existing.series_id = series.id
        WHERE document.source_file_url = 'generated'
          AND NOT EXISTS (
              SELECT 1 FROM interview_sessions session WHERE session.document_id = document.id
          )
        ON CONFLICT (series_id, round_number) DO NOTHING
        """
    )

    op.execute(
        """
        UPDATE documents document
        SET
            interview_round_id = (
                SELECT round.id
                FROM interview_rounds round
                WHERE round.guide_document_id = document.id
                ORDER BY round.round_number DESC
                LIMIT 1
            ),
            guide_version = CASE
                WHEN EXISTS (
                    SELECT 1 FROM interview_sessions session
                    WHERE session.document_id = document.id
                ) THEN 1
                ELSE COALESCE((
                    SELECT round.round_number
                    FROM interview_rounds round
                    WHERE round.guide_document_id = document.id
                    ORDER BY round.round_number DESC
                    LIMIT 1
                ), 1)
            END,
            is_frozen = EXISTS (
                SELECT 1 FROM interview_sessions session WHERE session.document_id = document.id
            )
        WHERE EXISTS (
              SELECT 1 FROM interview_rounds round WHERE round.guide_document_id = document.id
          )
        """
    )

    op.execute(
        """
        UPDATE interview_insight_memos memo
        SET
            interview_round_id = session.interview_round_id,
            interview_series_id = round.series_id
        FROM interview_sessions session
        LEFT JOIN interview_rounds round ON round.id = session.interview_round_id
        WHERE memo.session_id = session.id
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_insight_memos_interview_round_id", table_name="interview_insight_memos"
    )
    op.drop_index(
        "ix_interview_insight_memos_interview_series_id", table_name="interview_insight_memos"
    )
    op.drop_constraint(
        "fk_insight_memos_interview_round_id", "interview_insight_memos", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_insight_memos_interview_series_id", "interview_insight_memos", type_="foreignkey"
    )
    op.drop_column("interview_insight_memos", "interview_round_id")
    op.drop_column("interview_insight_memos", "interview_series_id")

    op.drop_index("ix_interview_sessions_interview_round_id", table_name="interview_sessions")
    op.execute(
        "ALTER TABLE interview_sessions "
        "DROP CONSTRAINT IF EXISTS uq_interview_sessions_interview_round_id"
    )
    op.drop_constraint(
        "fk_interview_sessions_interview_round_id", "interview_sessions", type_="foreignkey"
    )
    op.drop_column("interview_sessions", "interview_round_id")

    op.drop_index("ix_documents_is_frozen", table_name="documents")
    op.drop_index("ix_documents_interview_round_id", table_name="documents")
    op.drop_constraint("fk_documents_interview_round_id", "documents", type_="foreignkey")
    op.drop_column("documents", "is_frozen")
    op.drop_column("documents", "guide_version")
    op.drop_column("documents", "interview_round_id")

    op.drop_index("ix_interview_rounds_status", table_name="interview_rounds")
    op.drop_index("ix_interview_rounds_guide_document_id", table_name="interview_rounds")
    op.drop_index("ix_interview_rounds_series_id", table_name="interview_rounds")
    op.drop_table("interview_rounds")

    op.drop_index("ix_interview_series_status", table_name="interview_series")
    op.drop_index("ix_interview_series_stakeholder_profile_id", table_name="interview_series")
    op.drop_index("ix_interview_series_project_id", table_name="interview_series")
    op.drop_table("interview_series")
