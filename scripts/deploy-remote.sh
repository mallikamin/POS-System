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
# NEVER `|| true` here. That single suppression hid a stale backend on this
# box: `git pull` had been failing on a locally-modified nginx.demo.conf while
# the deploy reported success, so the frontend kept shipping (it is rsync'd,
# not pulled) and the backend silently stayed on an old commit. Discovered
# 2026-07-28 when a migration that had "deployed" was not in the database.
#
# A deploy that cannot get the code it was asked to deploy has failed. Say so.
if ! git pull origin main; then
  echo
  echo "FAILED: git pull was refused. The server has local changes to a file"
  echo "the incoming commits also touch. Resolve it deliberately -- do NOT"
  echo "'git checkout --' blindly: .env.demo is tracked here and holds the"
  echo "live credentials. Compare with 'git diff FETCH_HEAD -- <file>' first;"
  echo "if the working tree already matches the incoming version, stash that"
  echo "one path, pull, and drop the stash."
  exit 1
fi

echo "==> Installing pre-built frontend"
rm -rf frontend/dist
cp -r frontend-dist frontend/dist

# .dockerignore lists `dist`, which would exclude the very artifact we just
# uploaded. Drop the line for the build, then restore it FROM GIT.
#
# It used to be restored with `echo dist >>`, which does not necessarily
# reproduce the original file -- and left it permanently dirty in git. That
# matters: a dirty tracked file is exactly what blocks `git pull` and stalls
# every future deploy. Restoring from git leaves no drift behind.
sed -i '/^dist$/d' frontend/.dockerignore
docker build -t pos-system-frontend -f frontend/Dockerfile.prebuilt frontend/
git checkout -- frontend/.dockerignore

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

# --- nginx: RELOAD, never recreate (OI-92 item 1, second half) --------------
# This step used to be `up -d --no-deps --force-recreate nginx`, and it was the
# single reason a deploy needed a closed-shop window. nginx is SHARED: it serves
# Chick Shack's tablet, Orbit CRM and orbit-voice. Dropping the container drops
# all of them, so a POS deploy could take down two other businesses.
#
# It was only ever done because nginx resolved `backend` and `frontend` to
# container IPs at config load and cached them, so recreating those two left
# nginx pointing at dead addresses. That is fixed: every proxy_pass now goes
# through a variable and re-resolves per request via Docker's embedded DNS.
# nginx therefore does NOT need replacing when backend or frontend move.
#
# What it still needs is to pick up CONFIG changes. `nginx -s reload` does that
# gracefully: the master process starts new workers on the new config and lets
# the old ones finish their in-flight requests. No container operation, no
# dropped connections, no mounts at risk, and nothing for Orbit CRM to notice.
#
# The order below matters. `nginx -t` runs FIRST and the reload only happens if
# it passes, so a broken config leaves the site serving the last good one
# instead of taking it down.
if [ ! -f /root/orbit-crm/voice.conf ]; then
  echo "REFUSING to touch nginx: /root/orbit-crm/voice.conf is missing."
  echo "Its mount would have become a DIRECTORY and nginx would refuse to load."
  exit 1
fi

if [ -z "$(docker ps -q -f name='^pos-system-nginx-1$')" ]; then
  # Only case that still needs a container operation: nginx is not running at
  # all, so there is nothing to reload and nothing to interrupt.
  echo "==> nginx is not running. Starting it."
  dc up -d --no-deps nginx
else
  echo "==> Testing nginx config before applying it"
  if ! docker exec pos-system-nginx-1 nginx -t; then
    echo
    echo "FAILED: the new nginx config is invalid. NOTHING was applied and the"
    echo "running config is untouched, so all sites are still up. Fix the"
    echo "config and deploy again."
    exit 1
  fi

  echo "==> Reloading nginx gracefully (no container replaced)"
  docker exec pos-system-nginx-1 nginx -s reload
fi

dc ps
echo "==> Deployment complete"
