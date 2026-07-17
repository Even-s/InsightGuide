"""Smoke-check the clean v2 baseline schema.

The goal is not to replace Alembic autogenerate checks; it is a small,
deploy-friendly guard that proves the connected database has the new
InsightGuide baseline shape and no retired compatibility tables/columns.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import engine


REQUIRED_TABLES = {
    "users",
    "projects",
    "stakeholder_profiles",
    "interview_series",
    "interview_rounds",
    "documents",
    "interview_themes",
    "question_cards",
    "prep_sessions",
    "interview_sessions",
    "live_utterances",
    "interview_card_states",
    "card_coverage_evaluations",
    "card_criterion_evidence",
    "interview_insight_memos",
    "interview_round_aggregates",
    "requirement_evidence_matrices",
    "brd_readiness_reports",
}

FORBIDDEN_TABLES = {
    "sections",
    "slides",
    "decks",
    "topic_cards",
    "presentation_sessions",
    "final_utterances",
    "question_answers",
    "question_instances",
    "transcript_revisions",
    "utterance_alignments",
    "diarization_jobs",
    "evidence_matrix_entries",
    "brd_drafts",
    "requirements",
}

REQUIRED_COLUMNS = {
    "documents": {"interview_round_id", "guide_version", "is_frozen"},
    "interview_sessions": {
        "current_theme_id",
        "active_card_id",
        "active_card_source",
        "pending_answer_buffer",
    },
    "live_utterances": {"theme_id", "asked_card_ids", "transcript"},
    "question_cards": {"interview_theme_id", "coverage_rule", "question_text"},
    "interview_insight_memos": {"question_summaries"},
    "interview_round_aggregates": {"coverage_snapshot", "evidence_snapshot", "latest_memo_id"},
    "brd_readiness_reports": {"ready_chapters", "insufficient_chapters"},
}

FORBIDDEN_COLUMNS = {
    "documents": {"deck_id", "deck_title", "presentation_session_id"},
    "prep_sessions": {"deck_id"},
    "interview_sessions": {"current_section_id", "active_card_hint_id", "interview_scope"},
    "live_utterances": {
        "section_id",
        "speaker",
        "speaker_role",
        "speaker_label",
        "is_partial",
    },
    "question_cards": {"section_id", "topic_card_id"},
    "interview_themes": {"source_section_ids"},
    "interview_insight_memos": {"qa_summaries"},
    "brd_readiness_reports": {"ready_sections", "insufficient_sections"},
}


def main() -> None:
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except SQLAlchemyError as exc:
        print(
            "Clean baseline schema smoke check could not connect to the database.",
            file=sys.stderr,
        )
        print(f"  - {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    missing_tables = sorted(REQUIRED_TABLES - existing_tables)
    forbidden_tables = sorted(FORBIDDEN_TABLES & existing_tables)

    column_failures: list[str] = []
    for table_name, required_columns in REQUIRED_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            column_failures.append(
                f"{table_name}: missing required columns {', '.join(missing_columns)}"
            )

    forbidden_column_failures: list[str] = []
    for table_name, forbidden_columns in FORBIDDEN_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        present_forbidden_columns = sorted(forbidden_columns & existing_columns)
        if present_forbidden_columns:
            forbidden_column_failures.append(
                f"{table_name}: forbidden columns {', '.join(present_forbidden_columns)}"
            )

    failures = []
    if missing_tables:
        failures.append(f"Missing required tables: {', '.join(missing_tables)}")
    if forbidden_tables:
        failures.append(f"Forbidden retired tables exist: {', '.join(forbidden_tables)}")
    failures.extend(column_failures)
    failures.extend(forbidden_column_failures)

    if failures:
        print("Clean baseline schema smoke check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        raise SystemExit(1)

    print(
        "Clean baseline schema smoke check passed "
        f"({len(REQUIRED_TABLES)} required tables, {len(FORBIDDEN_TABLES)} retired tables absent)."
    )


if __name__ == "__main__":
    main()
