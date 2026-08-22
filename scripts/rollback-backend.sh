#!/usr/bin/env bash
#
# Roll the POS backend back to a previously tagged image. Runs ON 159.65.158.26.
#
#   bash scripts/rollback-backend.sh pre-oi89
#
# Why this exists (2026-08-22, OI-89/OI-90): a print-format change had to be
# deployed DURING service, because the only way to test a kitchen ticket is to
# print one in the shop. A rollback that takes the CI pipeline (~5 min: revert,
# push, build) is too slow while orders are landing. This swaps the backend
# back to the pre-deploy image in about 30 seconds.
#
# Before the deploy, the running image is tagged:
#     docker tag pos-system-backend:latest pos-system-backend:<tag>
# This script re-points `latest` at that tag and recreates the container from
# it WITHOUT building, then recreates nginx (it caches the backend's IP, and a
# `restart` does not clear that -- see deploy-remote.sh).
#
# ⚠️ Only valid when the deploy carried NO migration. The DB is not touched
# here; an image from before a migration would meet a schema it does not know.
# Check `alembic history` / the deploy notes before using it after a migration.
#
# ⚠️ This is a container rollback, not a code rollback. `git` on the server and
# on origin still point at the new commit, so the NEXT deploy would rebuild the
# rolled-back change straight back in. Follow up with `git revert` + push (or a
# fix-forward) before anything else is deployed.

set -euo pipefail

TAG="${1:?usage: rollback-backend.sh <image tag, e.g. pre-oi89>}"
IMAGE="pos-system-backend"

cd /root/pos-system
dc() { docker compose -f docker-compose.demo.yml --env-file .env.demo "$@"; }

if ! docker image inspect "$IMAGE:$TAG" >/dev/null 2>&1; then
  echo "No image $IMAGE:$TAG on this box. Nothing to roll back to."
  docker images --format '{{.Repository}}:{{.Tag}}  {{.CreatedAt}}' | grep "^$IMAGE" || true
  exit 1
fi

echo "==> backend container is currently running image $(docker inspect -f '{{.Image}}' pos-system-backend-1 | cut -c8-19)"
echo "==> rolling back to $IMAGE:$TAG ($(docker inspect -f '{{.Id}}' "$IMAGE:$TAG" | cut -c8-19))"
docker tag "$IMAGE:$TAG" "$IMAGE:latest"

echo "==> Recreating backend from the tagged image (no build)"
dc up -d --no-deps --no-build --force-recreate backend

echo "==> Waiting for backend to report healthy"
state=starting
for _ in $(seq 1 30); do
  state=$(docker inspect -f '{{.State.Health.Status}}' pos-system-backend-1 2>/dev/null || echo starting)
  [ "$state" = "healthy" ] && break
  sleep 2
done
echo "    backend: $state"

# Same guard as deploy-remote.sh: nginx is shared with Orbit CRM and a missing
# voice.conf on the host would take both sites down.
if [ ! -f /root/orbit-crm/voice.conf ]; then
  echo "REFUSING to recreate nginx: /root/orbit-crm/voice.conf is missing."
  echo "Backend is rolled back but nginx may hold its old IP; expect 502s"
  echo "until nginx is recreated deliberately."
  exit 1
fi

echo "==> Recreating nginx"
dc up -d --no-deps --force-recreate nginx
docker exec pos-system-nginx-1 nginx -t

dc ps
echo "==> Rollback complete. Remember: origin/main still has the new commit."
