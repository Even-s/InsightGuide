#!/usr/bin/env bash
# Recreate the Alembic migration chain as a single clean v2 baseline.
#
# This script is intentionally destructive to migration source files and to the
# configured baseline-generation database schema. Use a throwaway database via
# CLEAN_BASELINE_DATABASE_URL unless you explicitly intend to reset DATABASE_URL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSIONS_DIR="${BACKEND_DIR}/app/db/migrations/versions"
ARCHIVES_ROOT="${BACKEND_DIR}/app/db/migration_archives"
REV_ID="${CLEAN_BASELINE_REV_ID:-0001_clean_v2_baseline}"
MESSAGE="${CLEAN_BASELINE_MESSAGE:-clean v2 baseline}"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
ARCHIVE_DIR="${ARCHIVES_ROOT}/archive_${TIMESTAMP}"

cd "${BACKEND_DIR}"

if [[ "${RESET_INSIGHTGUIDE_MIGRATIONS:-}" != "yes" ]]; then
  cat >&2 <<EOF
Refusing to recreate migrations without confirmation.

Set:
  RESET_INSIGHTGUIDE_MIGRATIONS=yes

Recommended:
  CLEAN_BASELINE_DATABASE_URL=postgresql://...throwaway...

Then rerun:
  RESET_INSIGHTGUIDE_MIGRATIONS=yes \\
  CLEAN_BASELINE_DATABASE_URL=postgresql://... \\
  ./scripts/create_clean_baseline.sh
EOF
  exit 1
fi

BASELINE_DATABASE_URL="${CLEAN_BASELINE_DATABASE_URL:-${DATABASE_URL:-}}"
if [[ -z "${BASELINE_DATABASE_URL}" ]]; then
  echo "Missing CLEAN_BASELINE_DATABASE_URL or DATABASE_URL." >&2
  exit 1
fi

if [[ -z "${CLEAN_BASELINE_DATABASE_URL:-}" && "${ALLOW_DATABASE_URL_BASELINE_RESET:-}" != "yes" ]]; then
  cat >&2 <<EOF
Refusing to reset DATABASE_URL for baseline generation.

Use CLEAN_BASELINE_DATABASE_URL for a throwaway database, or set:
  ALLOW_DATABASE_URL_BASELINE_RESET=yes
EOF
  exit 1
fi

if [[ ! -x "venv/bin/python" ]]; then
  echo "backend/venv is missing. Run ./insightguide.sh setup first." >&2
  exit 1
fi

mkdir -p "${VERSIONS_DIR}" "${ARCHIVE_DIR}"
find "${VERSIONS_DIR}" -maxdepth 1 -type f -name '*.py' -exec mv {} "${ARCHIVE_DIR}/" \;
find "${VERSIONS_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} +

export DATABASE_URL="${BASELINE_DATABASE_URL}"

venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
with engine.begin() as connection:
    connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    connection.execute(text("CREATE SCHEMA public"))
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
PY

venv/bin/alembic revision \
  --autogenerate \
  --rev-id "${REV_ID}" \
  -m "${MESSAGE}"

venv/bin/alembic upgrade head
venv/bin/python scripts/bootstrap_database.py
venv/bin/python scripts/smoke_clean_baseline_schema.py

echo "Clean baseline migration created:"
find "${VERSIONS_DIR}" -maxdepth 1 -type f -name "${REV_ID}_*.py" -print
echo "Archived old migration files in: ${ARCHIVE_DIR}"
