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
# Usage: bash scripts/deploy-remote.sh [<git sha>]
#   CI passes the sha it built the frontend for. By hand, omit it and the
#   script deploys whatever `git pull` lands on -- but the frontend build for
#   that commit must already be in www/releases/<sha>/ (see below).

set -euo pipefail

cd /root/pos-system

COMPOSE_FILE="docker-compose.demo.yml"
ENV_FILE=".env.demo"
dc() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

WWW=/root/pos-system/www
WANT_SHA="${1:-}"

# --- Frontend build must already be here, BEFORE anything is touched -------
# CI builds on the GitHub runner (never on this 2GB box) and rsyncs dist/ to
# www/releases/<sha>/ before calling this script. Check first, so a missing
# build fails before `git pull` has moved the code from under the containers.
if [ -n "$WANT_SHA" ] && [ ! -f "$WWW/releases/$WANT_SHA/index.html" ]; then
  echo "FAILED: no frontend build for $WANT_SHA at $WWW/releases/$WANT_SHA/."
  echo "CI uploads it there before running this script. Nothing was touched."
  exit 1
fi

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

SHA=$(git rev-parse HEAD)
if [ -n "$WANT_SHA" ] && [ "$WANT_SHA" != "$SHA" ]; then
  echo "FAILED: asked to deploy $WANT_SHA but 'git pull' landed on $SHA."
  echo "A later push has moved main; that push's own deploy run will ship it."
  echo "Code was pulled; no container was rebuilt and the frontend was not"
  echo "switched, so the site is still serving what it served before."
  exit 1
fi
RELEASE="$WWW/releases/$SHA"
if [ ! -f "$RELEASE/index.html" ]; then
  echo "FAILED: no frontend build for $SHA at $RELEASE/."
  echo "Build it somewhere with RAM and rsync dist/ to that path, then re-run."
  exit 1
fi

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

# --- Frontend: atomic symlink swap (OI-92 item 2) ---------------------------
# nginx serves $WWW/current directly (bind-mounted read-only as /var/www/pos).
# `current` is a symlink into releases/, and switching it is ONE rename(2):
# a request either sees the old release or the new one, never a mix, and no
# container is touched. This is what made the frontend half of a deploy
# invisible to whoever is on the site.
#
# ⚠️ `ln -sfn` is NOT atomic. It unlinks the old link and then creates the new
# one, and a request in that gap gets a 404 for everything. Create the new
# link under a temporary name and `mv -T` it over the old one instead.
#
# The symlink target is RELATIVE so it resolves inside the container, where
# the same tree is mounted at a different path.
echo "==> Switching the frontend to $SHA"
mkdir -p "$WWW/releases"
if [ -e "$WWW/current" ] && [ ! -L "$WWW/current" ]; then
  echo "FAILED: $WWW/current exists and is not a symlink. Refusing to guess."
  exit 1
fi
tmp_link="$WWW/.current.$$"
ln -s "releases/$SHA" "$tmp_link"
mv -T "$tmp_link" "$WWW/current"
echo "    current -> $(readlink "$WWW/current")"

# Keep the five newest releases so a rollback is a symlink swap away, and so
# a tab that loaded an older index.html can still fetch that release's chunks
# for a while. Never delete the one being served.
echo "==> Pruning old releases (keeping the 5 newest)"
ls -1t "$WWW/releases" | tail -n +6 | while read -r old; do
  [ "$old" = "$SHA" ] && continue
  echo "    removing releases/$old"
  rm -rf "$WWW/releases/$old"
done

# --- nginx: touch it as little as possible (OI-92 items 1 and 2) ------------
# nginx is SHARED: it serves Chick Shack's tablet, Orbit CRM and orbit-voice.
# Every deploy used to `--force-recreate` it, so a POS deploy could take two
# other businesses down, and that was the single reason a deploy needed a
# closed-shop window. Every proxy_pass now goes through a variable and
# re-resolves per request, so a replaced backend needs NO nginx action, and
# the frontend swap above needs none either.
#
# What is left is CONFIG changes, and there is a trap. The config is a
# single-FILE bind mount, and `git pull` replaces the file's inode, so the
# running container keeps reading the OLD inode: `nginx -s reload` inside it
# would reload the config it already has, and report success. The only way
# to pick up a pulled config change is a new container. So: compare the
# config the container actually sees with the one on disk, and recreate
# ONLY when they differ (or when the compose definition gained a mount the
# running container lacks). An app-only deploy, the common case, does not
# touch nginx at all.
if [ ! -f /root/orbit-crm/voice.conf ]; then
  echo "REFUSING to touch nginx: /root/orbit-crm/voice.conf is missing."
  echo "Its mount would have become a DIRECTORY and nginx would refuse to load."
  exit 1
fi

nginx_mounts() {
  docker inspect -f '{{range .Mounts}}{{.Destination}}{{"\n"}}{{end}}' pos-system-nginx-1 2>/dev/null
}

if [ -z "$(docker ps -q -f name='^pos-system-nginx-1$')" ]; then
  # nginx is not running at all: nothing to interrupt, just start it.
  echo "==> nginx is not running. Starting it."
  dc up -d --no-deps nginx
else
  recreate_reason=""
  if ! nginx_mounts | grep -qx /var/www/pos; then
    recreate_reason="the running container has no /var/www/pos mount (frontend releases)"
  fi
  live_md5=$(docker exec pos-system-nginx-1 md5sum /etc/nginx/conf.d/default.conf | cut -d' ' -f1)
  disk_md5=$(md5sum docker/nginx/nginx.demo.conf | cut -d' ' -f1)
  if [ "$live_md5" != "$disk_md5" ]; then
    recreate_reason="${recreate_reason:+$recreate_reason; }nginx.demo.conf changed on disk and a reload cannot see it"
  fi

  if [ -z "$recreate_reason" ]; then
    echo "==> nginx config unchanged. nginx NOT touched."
    docker exec pos-system-nginx-1 nginx -t
  else
    echo "==> nginx must be RECREATED: $recreate_reason"
    echo "    mounts before:"
    docker inspect -f '{{range .Mounts}}      {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' pos-system-nginx-1

    # Prove the new config loads BEFORE dropping the live container, in a
    # throwaway container that borrows the live one's mounts (certs, voice.conf)
    # plus the releases tree. A bad config then fails here, with every site
    # still up, instead of leaving nginx in a restart loop.
    echo "==> Testing the new nginx config in a throwaway container"
    if ! docker run --rm --volumes-from pos-system-nginx-1 \
         -v /root/pos-system/www:/var/www/pos:ro \
         nginx:1.27-alpine nginx -t; then
      echo
      echo "FAILED: the new nginx config is invalid. The running nginx is"
      echo "untouched and every site is still up. Fix the config and deploy again."
      exit 1
    fi

    echo "==> Recreating nginx (all hostnames blip for a few seconds)"
    dc up -d --no-deps --force-recreate nginx
    echo "    mounts after:"
    docker inspect -f '{{range .Mounts}}      {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' pos-system-nginx-1
    for m in /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/voice.conf /etc/letsencrypt /var/www/certbot /var/www/pos; do
      if ! nginx_mounts | grep -qx "$m"; then
        echo "FAILED: nginx came back WITHOUT the $m mount. Check docker-compose.demo.yml."
        exit 1
      fi
    done
  fi
fi

# --- The frontend container is retired --------------------------------------
# Only once nginx is serving the static tree itself. Left over from before
# OI-92 item 2; compose no longer defines it, so it would sit as an orphan.
if [ -n "$(docker ps -a -q -f name='^pos-system-frontend-1$')" ]; then
  echo "==> Removing the retired frontend container"
  docker rm -f pos-system-frontend-1 >/dev/null
  docker image rm pos-system-frontend >/dev/null 2>&1 || true
fi

dc ps
echo "==> Deployment complete"
