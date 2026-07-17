#!/usr/bin/env bash
# Reset the EC2 prototype database rows and MinIO files without changing schema.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EC2_DIR="${SCRIPT_DIR}/ec2"
ENV_FILE="${ENV_FILE:-"${EC2_DIR}/.env"}"
COMPOSE_FILE="${EC2_DIR}/docker-compose.yml"

if [[ "${RESET_INSIGHTGUIDE_PROTOTYPE:-}" != "yes" ]]; then
  cat >&2 <<EOF
Refusing to reset prototype data without confirmation.

Set:
  RESET_INSIGHTGUIDE_PROTOTYPE=yes

Then rerun:
  RESET_INSIGHTGUIDE_PROTOTYPE=yes ./deploy/reset-prototype-data.sh
EOF
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}." >&2
  exit 1
fi

compose=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

"${compose[@]}" up -d postgres redis minio minio-init
"${compose[@]}" run --rm backend \
  python scripts/smoke_clean_baseline_schema.py
"${compose[@]}" run --rm backend \
  python scripts/reset_dev_data.py --yes --include-users --ignore-s3-errors

echo "Prototype data reset complete."
