#!/usr/bin/env bash
#
# The server side of a production deploy. Runs ON 159.65.158.26.
#
# ⚠️ WHY THIS IS A FILE AND NOT A HEREDOC.
#
# This logic used to live inline in deploy-production.yml as:
#
#     ssh host << 'ENDSSH'
#       ...
#       docker compose exec -T postgres pg_dump > backup.sql
#       docker compose exec -T backend alembic upgrade head
#     ENDSSH
#
# The remote shell reads that script FROM STDIN. `docker compose exec` also
# reads stdin -- so pg_dump silently swallowed every remaining line of the
# script as its own input. The deploy then "succeeded" having simply stopped:
# the migration step and everything after it never ran, with no error anywhere.
#
# Confirmed on 2026-07-28: a pre_migrate backup existed with a matching
# timestamp while `alembic upgrade head` had demonstrably not run, and nginx
# was still the container from three hours earlier. Migrations were only ever
# applied because the backend's own start.sh runs them at boot -- luck, not
# design.
#
# As a file executed by path, stdin is free and every line runs.
#
# Safe to run by hand: bash scripts/deploy-remote.sh

set -euo pipefail

cd /root/pos-system

COMPOSE_FILE="docker-compose.demo.yml"
ENV_FILE=".env.demo"
dc() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

echo "==> Pulling code"
git pull origin main || true

echo "==> Installing pre-built frontend"
rm -rf frontend/dist
cp -r frontend-dist frontend/dist

# .dockerignore lists `dist`, which would exclude the very artifact we just
# uploaded. Drop the line for the build, then restore it.
sed -i '/^dist$/d' frontend/.dockerignore
docker build -t pos-system-frontend -f frontend/Dockerfile.prebuilt frontend/
echo "dist" >> frontend/.dockerignore

echo "==> Recreating frontend"
dc up -d --no-deps --force-recreate frontend

echo "==> Rebuilding backend"
dc up -d --no-deps --build backend

echo "==> Waiting for backend to report healthy"
for _ in $(seq 1 30); do
  state=$(docker inspect -f '{{.State.Health.Status}}' pos-system-backend-1 2>/dev/null || echo starting)
  [ "$state" = "healthy" ] && break
  sleep 2
done
echo "    backend: ${state:-unknown}"

# --- Database backup, then migrations ---------------------------------------
# This database has been lost once already (2026-03-26). Back up first, without
# exception, and refuse to migrate against an unusable dump -- an empty backup
# is worse than a missing one, because it gets trusted.
echo "==> Backing up the database"
mkdir -p backups
BACKUP="backups/pre_migrate_$(date +%Y-%m-%d_%H%M%S).sql"
dc exec -T postgres pg_dump -U pos_admin -d pos_system > "$BACKUP" < /dev/null

if [ ! -s "$BACKUP" ]; then
  echo "Backup is empty ($BACKUP). Refusing to migrate."
  exit 1
fi
echo "    backup OK: $BACKUP ($(wc -c < "$BACKUP") bytes)"

echo "==> Running migrations"
dc exec -T backend alembic upgrade head < /dev/null

# --- nginx: LAST, and only after proving its mounts -------------------------
# Recreating frontend and backend above gave them new container IPs. nginx
# resolved the old ones at startup and caches them, so skipping this leaves a
# 502 for someone to fix by hand. `restart` does NOT clear that cache.
#
# nginx is SHARED INFRASTRUCTURE -- it serves Orbit CRM too, and on 2026-03-26
# recreating it without its voice.conf mount took orbit-voice down for ~20
# minutes. Compose recreation is safe because all four mounts are declared in
# the compose file, but a missing voice.conf on the HOST would make Docker
# create a DIRECTORY at that path and nginx would refuse to start, taking BOTH
# sites down. So prove it is a file first.
if [ ! -f /root/orbit-crm/voice.conf ]; then
  echo "REFUSING to recreate nginx: /root/orbit-crm/voice.conf is missing."
  echo "Recreating now would drop Orbit CRM's config and 502 both sites."
  exit 1
fi

echo "==> Recreating nginx"
dc up -d --no-deps --force-recreate nginx
docker exec pos-system-nginx-1 nginx -t

dc ps
echo "==> Deployment complete"
