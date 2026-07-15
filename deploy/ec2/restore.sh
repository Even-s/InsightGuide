#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENV_FILE=${ENV_FILE:-"${SCRIPT_DIR}/.env"}
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
backup_root=${BACKUP_DIR:-"${SCRIPT_DIR}/backups"}
backup_id=${1:-}

if [[ -z ${backup_id} ]]; then
  echo "Usage: RESTORE_CONFIRM=restore-<backup-id> $0 <backup-id>" >&2
  exit 1
fi

backup_dir="${backup_root}/${backup_id}"
if [[ ! -s "${backup_dir}/postgres.dump" || ! -d "${backup_dir}/minio" ]]; then
  echo "Backup ${backup_dir} is incomplete or missing." >&2
  exit 1
fi

if [[ ${RESTORE_CONFIRM:-} != "restore-${backup_id}" ]]; then
  echo "Restore replaces the current PostgreSQL and MinIO data." >&2
  echo "Set RESTORE_CONFIRM=restore-${backup_id} to continue." >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

compose=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

echo "Stopping application writers..."
"${compose[@]}" stop backend worker web || true
"${compose[@]}" up -d --wait postgres redis minio
"${compose[@]}" run --rm minio-init

echo "Restoring PostgreSQL..."
"${compose[@]}" exec -T postgres \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  --clean --if-exists --no-owner --no-privileges \
  < "${backup_dir}/postgres.dump"

echo "Restoring MinIO bucket..."
"${compose[@]}" run --rm --no-deps \
  -v "${backup_dir}/minio:/backup:ro" \
  --entrypoint /bin/sh minio-init -ec '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
    mc mirror --overwrite --remove /backup "local/$S3_BUCKET_NAME"
  '

echo "Applying current migrations and restarting services..."
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d --wait backend worker web

echo "Restore completed from ${backup_id}."
