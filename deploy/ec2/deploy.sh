#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENV_FILE=${ENV_FILE:-"${SCRIPT_DIR}/.env"}
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy .env.example to .env and fill in the values." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

required=(
  APP_SITE_ADDRESS FILES_SITE_ADDRESS APP_ORIGIN FILES_ORIGIN ACME_EMAIL
  WEB_HTTP_BIND WEB_HTTPS_BIND MINIO_API_BIND POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
  REDIS_PASSWORD SECRET_KEY MINIO_ROOT_USER MINIO_ROOT_PASSWORD S3_BUCKET_NAME
  OPENAI_API_KEY
)

for name in "${required[@]}"; do
  if [[ -z ${!name:-} ]]; then
    echo "Required setting ${name} is empty in ${ENV_FILE}." >&2
    exit 1
  fi
done

if grep -Eq 'replace-me|replace_with|example\.com' "${ENV_FILE}"; then
  echo "The environment file still contains placeholder values." >&2
  exit 1
fi

if [[ ${#SECRET_KEY} -lt 48 ]]; then
  echo "SECRET_KEY must be at least 48 characters." >&2
  exit 1
fi

compose=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

echo "Validating Docker Compose configuration..."
"${compose[@]}" config --quiet

echo "Building production images..."
"${compose[@]}" build --pull backend web

echo "Starting PostgreSQL, Redis, and MinIO..."
"${compose[@]}" up -d --wait postgres redis minio

echo "Creating the private MinIO bucket and CORS policy..."
"${compose[@]}" run --rm minio-init

echo "Applying database migrations and enforcing the clean schema..."
"${compose[@]}" run --rm migrate

echo "Starting API, worker, and frontend gateway..."
"${compose[@]}" up -d --wait --remove-orphans backend worker web

echo "Checking the API inside the container network..."
"${compose[@]}" exec -T backend python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=5)"

echo
"${compose[@]}" ps
echo
echo "Deployment completed."
echo "Application: ${APP_ORIGIN}"
echo "Private files: ${FILES_ORIGIN}"
echo
if [[ ${APP_ORIGIN} == https://* ]]; then
  echo "Caddy may need a few minutes to obtain the first TLS certificates."
else
  echo "Private mode is active. Start the local SSM tunnels before opening the application."
fi
