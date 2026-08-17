#!/usr/bin/env bash
# Deploy a committed change to production after the shop closes.
#
# Generalised from scripts/deploy_oi84.sh, which was written for one commit on
# 2026-08-16. Same refusals, same backup-first rule, same verify-by-effect.
#
#   bash scripts/deploy_after_close.sh <short-commit> "<target UTC>"
#   bash scripts/deploy_after_close.sh 565b42e "2026-08-17 21:30:00"
#   bash scripts/deploy_after_close.sh 565b42e --now      # skip the wait
#
# It refuses rather than guesses. Nothing is pushed until every precondition
# holds, the database is dumped and the dump is checked restorable first, and
# the result is verified by effect rather than by exit code.

set -uo pipefail

SERVER="root@159.65.158.26"
DEPLOY_TIMEOUT=900
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'

EXPECTED_COMMIT="${1:-}"
WHEN="${2:---now}"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }
die() { log "ABORTED: $*"; exit 1; }

[ -n "$EXPECTED_COMMIT" ] || die "usage: $0 <short-commit> [\"YYYY-MM-DD HH:MM:SS\" UTC | --now]"
cd "$(dirname "$0")/.." || die "cannot find the repo root"

# --- wait ------------------------------------------------------------------
if [ "$WHEN" != "--now" ]; then
  # Derived from the date string, never hand-computed: an earlier version of
  # this script carried a hardcoded epoch that was a year out, which would have
  # skipped the wait entirely and deployed mid-service.
  target=$(date -u -d "$WHEN" +%s 2>/dev/null) || die "cannot parse target time '$WHEN'"
  now=$(date -u +%s)
  wait_for=$(( target - now ))
  if [ "$wait_for" -gt 0 ]; then
    log "waiting ${wait_for}s until ${WHEN} UTC to deploy ${EXPECTED_COMMIT}"
    sleep "$wait_for"
  else
    log "target time already passed, proceeding"
  fi
fi

# --- preconditions ---------------------------------------------------------
log "=== PRECONDITIONS ==="
head_now=$(git rev-parse --short HEAD)
[ "$head_now" = "$EXPECTED_COMMIT" ] \
  || die "HEAD is $head_now, expected $EXPECTED_COMMIT. Something was committed after this was scheduled."
log "HEAD is $head_now, as scheduled"

branch=$(git rev-parse --abbrev-ref HEAD)
[ "$branch" = "main" ] || die "on branch $branch, not main"
git diff --cached --quiet || die "there is staged-but-uncommitted work"

ssh -o BatchMode=yes -o ConnectTimeout=15 "$SERVER" true 2>/dev/null \
  || die "cannot reach the server over ssh"
log "server reachable"

# ⚠️ The UK hour comes from the SERVER. Git Bash on Windows silently ignores a
# TZ prefix and returns local time with no error, so a guard written the obvious
# way reads the wrong clock while looking correct.
uk_hour=$(ssh "$SERVER" 'TZ=Europe/London date +%H')
[ -n "$uk_hour" ] || die "could not read the UK hour from the server"
if [ "$((10#$uk_hour))" -ge 15 ] && [ "$((10#$uk_hour))" -lt 22 ]; then
  die "it is ${uk_hour}:xx UK and the shop is open. Refusing to deploy during service."
fi
log "UK time is ${uk_hour}:xx, shop is shut"

# --- backup ----------------------------------------------------------------
# Taken even when the change carries no migration. It is cheap, and "this one
# does not touch the database" is exactly the assumption worth not making.
log "=== BACKUP ==="
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dump="/root/backups/pos_system_${stamp}_pre_${EXPECTED_COMMIT}.sql.gz"
ssh "$SERVER" "mkdir -p /root/backups && docker exec pos-system-postgres-1 sh -c 'pg_dump -U \$POSTGRES_USER \$POSTGRES_DB' | gzip > $dump" \
  || die "pg_dump failed"

verify=$(ssh "$SERVER" "gzip -t $dump && echo GZIP_OK; zcat $dump | grep -c '^COPY ' ; zcat $dump | tail -5 | grep -c 'PostgreSQL database dump complete'")
echo "$verify" | grep -q GZIP_OK || die "the dump is not valid gzip"
copies=$(echo "$verify" | sed -n '2p'); complete=$(echo "$verify" | sed -n '3p')
[ "$complete" = "1" ] || die "the dump has no completion marker, so it is truncated"
[ "${copies:-0}" -ge 30 ] || die "only ${copies} COPY blocks in the dump, expected 40+"
log "backup verified: $dump ($copies tables)"

# --- deploy ----------------------------------------------------------------
log "=== DEPLOY ==="
git push origin main || die "git push failed"
deadline=$(( $(date -u +%s) + DEPLOY_TIMEOUT ))
while :; do
  remote=$(ssh "$SERVER" 'cd ~/pos-system && git rev-parse --short HEAD' 2>/dev/null)
  [ "$remote" = "$EXPECTED_COMMIT" ] && { log "server is at $remote"; break; }
  [ "$(date -u +%s)" -ge "$deadline" ] && die "server still at ${remote:-unknown} after ${DEPLOY_TIMEOUT}s"
  sleep 20
done

# --- verify by effect ------------------------------------------------------
log "=== VERIFY ==="

# ⚠️ POLL, do not sample once. A ~90s 502 follows every deploy while the backend
# health check comes up; a single early probe reports a false failure. This is
# NOT the nginx stale-upstream-IP trap -- that was mis-diagnosed on 2026-08-16
# and disproved when a later deploy produced the same 502 without nginx being
# recreated at all. Do not recreate nginx on the strength of a 502 here.
log "-- waiting for the backend health check --"
for i in $(seq 1 15); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" https://eats.sitaratech.info/api/v1/health)
  [ "$code" = "200" ] && { log "   healthy after ~$((i*10))s"; break; }
  [ "$i" = "15" ] && log "   STILL $code after 150s -- investigate, do not assume"
  sleep 10
done

log "-- public URLs --"
for url in https://eats.sitaratech.info/api/v1/health \
           https://eats.sitaratech.info/api/v1/public/chick-shack/menu \
           https://chickshackg84.com/ ; do
  log "   $(curl -s -o /dev/null -w '%{http_code}' -A "$UA" "$url")  $url"
done

log "-- CORS on the real storefront origin --"
curl -s -D - -o /dev/null -A "$UA" -H "Origin: https://chickshackg84.com" \
  https://eats.sitaratech.info/api/v1/public/chick-shack/menu \
  | grep -i '^access-control-allow-origin' || log "   NO ACAO HEADER"

log "-- containers, and Orbit CRM which must be untouched --"
ssh "$SERVER" "docker ps --format '{{.Names}}\t{{.Status}}' | sort"

log "-- backend exceptions since deploy --"
ssh "$SERVER" "cd ~/pos-system && docker compose -f docker-compose.demo.yml --env-file .env.demo logs --since 10m backend 2>&1 | grep -ciE 'traceback|exception' || echo 0"

log "=== DONE. Read the output above before calling this deployed. ==="
log "Backup: $dump"
