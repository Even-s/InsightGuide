"""Reset InsightGuide application data for a clean v2 prototype baseline.

This script is intentionally destructive.  It clears application rows and,
by default, the configured S3/MinIO bucket content.  It keeps the schema and
Alembic version intact so it can be used after migrations have established a
clean baseline.

Safety guard:
    RESET_INSIGHTGUIDE_DATA=yes python scripts/reset_dev_data.py
    python scripts/reset_dev_data.py --yes
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401  Registers all SQLAlchemy models.
from app.core.config import settings
from app.db.session import Base, engine

RESET_CONFIRM_ENV = "RESET_INSIGHTGUIDE_DATA"
DEFAULT_USER_ID = "user_default"
DEFAULT_USER_EMAIL = "demo@insightguide.local"
DEFAULT_DEMO_PROJECT_ID = "proj_demo_clean_baseline"
DEFAULT_DEMO_PROJECT_TITLE = "InsightGuide Demo Project"
DEFAULT_LOCAL_ARTIFACT_DIRS = ("uploads",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear InsightGuide prototype data and uploaded/generated files."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help=f"Confirm destructive reset without requiring {RESET_CONFIRM_ENV}=yes.",
    )
    parser.add_argument(
        "--include-users",
        action="store_true",
        help="Also truncate users before recreating the default development user.",
    )
    parser.add_argument(
        "--skip-demo-project",
        action="store_true",
        help="Do not create the clean baseline demo project after reset.",
    )
    parser.add_argument(
        "--skip-s3",
        action="store_true",
        help="Do not delete objects from the configured S3/MinIO bucket.",
    )
    parser.add_argument(
        "--skip-local-files",
        action="store_true",
        help="Do not delete local uploaded/generated artifact directories.",
    )
    parser.add_argument(
        "--local-artifact-dir",
        action="append",
        default=list(DEFAULT_LOCAL_ARTIFACT_DIRS),
        help=(
            "Local artifact directory to clear, relative to backend/. "
            "Can be passed multiple times. Default: uploads."
        ),
    )
    parser.add_argument(
        "--s3-prefix",
        default="",
        help="Only delete S3 objects under this prefix. Default deletes the whole bucket.",
    )
    parser.add_argument(
        "--ignore-s3-errors",
        action="store_true",
        help="Continue even if S3/MinIO cleanup fails.",
    )
    return parser.parse_args()


def require_confirmation(args: argparse.Namespace) -> None:
    import os

    if args.yes or os.environ.get(RESET_CONFIRM_ENV) == "yes":
        return
    raise SystemExit(
        "Refusing to reset data without confirmation. "
        f"Pass --yes or set {RESET_CONFIRM_ENV}=yes."
    )


def quote_table_names(table_names: Iterable[str]) -> str:
    return ", ".join(f'"{name}"' for name in table_names)


def application_table_names(include_users: bool) -> list[str]:
    """Return current model tables that exist in the connected database."""
    existing = set(inspect(engine).get_table_names())
    names = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue
        if table.name == "users" and not include_users:
            continue
        names.append(table.name)

    # TRUNCATE handles dependencies with CASCADE, so ordering is not critical.
    return sorted(names)


def truncate_application_tables(include_users: bool) -> None:
    table_names = application_table_names(include_users=include_users)
    if not table_names:
        print("No application tables found to truncate.")
        return

    print("Truncating tables:")
    for name in table_names:
        print(f"  - {name}")

    with engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE TABLE {quote_table_names(table_names)} RESTART IDENTITY CASCADE")
        )


def ensure_default_user() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                "VALUES (:id, :email, 'not_used', NOW(), NOW()) "
                "ON CONFLICT (id) DO UPDATE SET "
                "email = EXCLUDED.email, updated_at = NOW()"
            ),
            {"id": DEFAULT_USER_ID, "email": DEFAULT_USER_EMAIL},
        )
    print(f"Ensured default user: {DEFAULT_USER_ID} <{DEFAULT_USER_EMAIL}>")


def ensure_demo_project() -> None:
    """Create the single clean baseline demo project after destructive reset."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO projects "
                "(id, user_id, title, description, brd_scope, status, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, :description, CAST(:brd_scope AS JSON), "
                "'active', NOW(), NOW()) "
                "ON CONFLICT (id) DO UPDATE SET "
                "user_id = EXCLUDED.user_id, "
                "title = EXCLUDED.title, "
                "description = EXCLUDED.description, "
                "brd_scope = EXCLUDED.brd_scope, "
                "status = EXCLUDED.status, "
                "updated_at = NOW()"
            ),
            {
                "id": DEFAULT_DEMO_PROJECT_ID,
                "user_id": DEFAULT_USER_ID,
                "title": DEFAULT_DEMO_PROJECT_TITLE,
                "description": (
                    "Clean baseline demo project created by reset_dev_data.py. "
                    "Use it to verify the v2 interview guide workflow."
                ),
                "brd_scope": json.dumps(
                    {
                        "business_domain": "醫療掛號服務",
                        "key_objectives": [
                            "驗證訪談大綱流程",
                            "確認 RoundAggregate 洞察輸出",
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        )
    print(f"Ensured demo project: {DEFAULT_DEMO_PROJECT_ID}")


def resolve_local_artifact_dir(raw_path: str) -> Path:
    candidate = (BACKEND_DIR / raw_path).resolve()
    try:
        candidate.relative_to(BACKEND_DIR)
    except ValueError as exc:
        raise SystemExit(
            f"Refusing to delete local artifact path outside backend/: {candidate}"
        ) from exc
    if candidate == BACKEND_DIR:
        raise SystemExit("Refusing to delete backend/ itself as a local artifact directory.")
    return candidate


def clear_local_artifacts(raw_paths: Iterable[str]) -> None:
    """Clear local uploaded/generated artifacts while preserving directories."""
    for raw_path in raw_paths:
        artifact_dir = resolve_local_artifact_dir(raw_path)
        if not artifact_dir.exists():
            artifact_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created empty local artifact directory: {artifact_dir}")
            continue
        if not artifact_dir.is_dir():
            raise SystemExit(f"Local artifact path is not a directory: {artifact_dir}")

        deleted_count = 0
        for child in artifact_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            deleted_count += 1
        print(f"Deleted {deleted_count} local artifact entries from {artifact_dir}.")


def clear_s3(prefix: str) -> int:
    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )

    deleted_count = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=prefix):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if not objects:
            continue
        client.delete_objects(Bucket=settings.S3_BUCKET_NAME, Delete={"Objects": objects})
        deleted_count += len(objects)

    return deleted_count


def main() -> None:
    args = parse_args()
    require_confirmation(args)

    truncate_application_tables(include_users=args.include_users)
    ensure_default_user()
    if args.skip_demo_project:
        print("Skipped clean baseline demo project creation.")
    else:
        ensure_demo_project()

    if args.skip_local_files:
        print("Skipped local uploaded/generated file cleanup.")
    else:
        clear_local_artifacts(args.local_artifact_dir)

    if args.skip_s3:
        print("Skipped S3/MinIO cleanup.")
        return

    try:
        deleted_count = clear_s3(args.s3_prefix)
        scope = f"prefix {args.s3_prefix!r}" if args.s3_prefix else "entire bucket"
        print(f"Deleted {deleted_count} S3/MinIO objects from {scope}.")
    except (BotoCoreError, ClientError) as exc:
        if args.ignore_s3_errors:
            print(f"Warning: S3/MinIO cleanup failed but was ignored: {exc}", file=sys.stderr)
            return
        raise


if __name__ == "__main__":
    main()
