#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------
# Standalone migration runner with database readiness wait.
#
# Usage:
#   ./scripts/migrate.sh                   # upgrade to head
#   ./scripts/migrate.sh revision --autogenerate -m "add users"
# -----------------------------------------------------------

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
MAX_RETRIES="${DB_WAIT_RETRIES:-30}"
RETRY_INTERVAL="${DB_WAIT_INTERVAL:-2}"

echo "==> Waiting for database at ${DB_HOST}:${DB_PORT}..."

retries=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; do
    retries=$((retries + 1))
    if [ "$retries" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: Database not ready after ${MAX_RETRIES} attempts. Exiting."
        exit 1
    fi
    echo "    Attempt ${retries}/${MAX_RETRIES} - retrying in ${RETRY_INTERVAL}s..."
    sleep "$RETRY_INTERVAL"
done

echo "==> Database is ready."

if [ $# -eq 0 ]; then
    echo "==> Running: alembic upgrade head"
    alembic upgrade head
else
    echo "==> Running: alembic $*"
    alembic "$@"
fi

echo "==> Migration complete."
