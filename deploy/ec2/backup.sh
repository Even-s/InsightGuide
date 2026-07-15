#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENV_FILE=${ENV_FILE:-"${SCRIPT_DIR}/.env"}
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_root=${BACKUP_DIR:-"${SCRIPT_DIR}/backups"}
backup_dir="${backup_root}/${timestamp}"
minio_dir="${backup_dir}/minio"
mkdir -p "${minio_dir}"

compose=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

echo "Backing up PostgreSQL..."
"${compose[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc \
  > "${backup_dir}/postgres.dump"

echo "Backing up MinIO bucket..."
"${compose[@]}" run --rm --no-deps \
  -v "${minio_dir}:/backup" \
  --entrypoint /bin/sh minio-init -ec '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
    mc mirror --overwrite "local/$S3_BUCKET_NAME" /backup
  '

(
  cd "${backup_dir}"
  find . -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

if [[ -n ${AWS_BACKUP_URI:-} ]]; then
  if command -v aws >/dev/null 2>&1; then
    echo "Uploading encrypted backup to ${AWS_BACKUP_URI}/${timestamp}/ ..."
    aws s3 cp "${backup_dir}" "${AWS_BACKUP_URI%/}/${timestamp}/" \
      --recursive --sse AES256
  else
    echo "AWS_BACKUP_URI is configured, but the AWS CLI is unavailable; local backup retained." >&2
  fi
fi

retention_days=${BACKUP_RETENTION_DAYS:-7}
find "${backup_root}" -mindepth 1 -maxdepth 1 -type d \
  -mtime "+${retention_days}" -exec rm -rf -- {} +

echo "Backup completed: ${backup_dir}"
