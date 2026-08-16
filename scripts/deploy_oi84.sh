#!/usr/bin/env bash
# Scheduled deploy of OI-84 (card intent at creation).
#
# Runs unattended at 02:30 Pakistan time = 21:30 UTC = 22:30 UK, thirty minutes
# after the shop closes. Malik scheduled it on 2026-08-16.
#
# Refuses rather than guesses. Every precondition is checked before anything is
# pushed, the database is dumped and the dump is verified restorable BEFORE the
# migration runs, and the result is verified by effect rather than by exit code.
#
#   bash scripts/deploy_oi84.sh          # sleeps until the target, then deploys
#   bash scripts/deploy_oi84.sh --now    # skip the wait (manual run)

set -uo pipefail

SERVER="root@159.65.158.26"
EXPECTED_COMMIT="baa63f3"
EXPECTED_ALEMBIC="v8w9x0y1z2a3"
# Derived from the date string, never hand-computed: the first draft of this
# script carried a hardcoded epoch that was a year out (2025), which would have
# made the script deploy instantly instead of waiting.
TARGET_UTC="2026-08-16 21:30:00"   # = 02:30 Pakistan, 22:30 UK, shop shut
TARGET_EPOCH=$(date -u -d "$TARGET_UTC" +%s 2>/dev/null) \
  || { echo "cannot parse the target time"; exit 1; }
DEPLOY_TIMEOUT=900               # 15 min for CI to build and recreate
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }
die() { log "ABORTED: $*"; exit 1; }

cd "$(dirname "$0")/.." || die "cannot find the repo root"

# --- wait ------------------------------------------------------------------
if [ "${1:-}" != "--now" ]; then
  now=$(date -u +%s)
  wait_for=$(( TARGET_EPOCH - now ))
  if [ "$wait_for" -gt 0 ]; then
    log "waiting ${wait_for}s until 21:30 UTC (02:30 PK, 22:30 UK, shop shut)"
    sleep "$wait_for"
  else
    log "target time already passed, proceeding"
  fi
fi

# --- preconditions ---------------------------------------------------------
log "=== PRECONDITIONS ==="

head_now=$(git rev-parse --short HEAD)
[ "$head_now" = "$EXPECTED_COMMIT" ] \
  || die "HEAD is $head_now, expected $EXPECTED_COMMIT. Someone committed since this was scheduled."
log "HEAD is $head_now, as scheduled"

branch=$(git rev-parse --abbrev-ref HEAD)
[ "$branch" = "main" ] || die "on branch $branch, not main"

git diff --cached --quiet || die "there is staged-but-uncommitted work"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$SERVER" true 2>/dev/null \
  || die "cannot reach the server over ssh"
log "server reachable"

# ⚠️ The UK hour is read off the SERVER, not this machine. Git Bash on Windows
# silently ignores the TZ prefix -- `TZ=Europe/London date` returns local time
# and no error -- so a guard written that way would have been reading the wrong
# clock while looking correct. The droplet has real tzdata and handles BST.
uk_hour=$(ssh "$SERVER" 'TZ=Europe/London date +%H')
[ -n "$uk_hour" ] || die "could not read the UK hour from the server"
# The shop trades 16:00-22:00 UK. Deploying recreates containers and nginx
# caches upstream IPs, so a push during service is a 502 window for customers.
if [ "$((10#$uk_hour))" -ge 15 ] && [ "$((10#$uk_hour))" -lt 22 ]; then
  die "it is ${uk_hour}:xx UK and the shop is open. Refusing to deploy during service."
fi
log "UK time is ${uk_hour}:xx, shop is shut"

# --- backup, BEFORE the migration -----------------------------------------
# Standing rule: pg_dump before anything that modifies the database, and this
# deploy runs an ALTER TABLE plus a backfill UPDATE. A dump that was never
# checked is not a backup, so it is verified restorable here, not assumed.
log "=== BACKUP ==="
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dump="/root/backups/pos_system_${stamp}_pre_OI84.sql.gz"

ssh "$SERVER" "mkdir -p /root/backups && docker exec pos-system-postgres-1 sh -c 'pg_dump -U \$POSTGRES_USER \$POSTGRES_DB' | gzip > $dump" \
  || die "pg_dump failed"

verify=$(ssh "$SERVER" "gzip -t $dump && echo GZIP_OK; zcat $dump | grep -c '^COPY ' ; zcat $dump | tail -5 | grep -c 'PostgreSQL database dump complete'")
echo "$verify" | grep -q GZIP_OK || die "the dump is not a valid gzip file"
copies=$(echo "$verify" | sed -n '2p')
complete=$(echo "$verify" | sed -n '3p')
[ "$complete" = "1" ] || die "the dump has no completion marker, so it is truncated"
[ "${copies:-0}" -ge 30 ] || die "the dump has only ${copies} COPY blocks, expected 40+. Refusing to migrate."
log "backup verified: $dump ($copies tables, completion marker present)"

# --- deploy ----------------------------------------------------------------
log "=== DEPLOY ==="
git push origin main || die "git push failed"
log "pushed. waiting for the server to report $EXPECTED_COMMIT"

deadline=$(( $(date -u +%s) + DEPLOY_TIMEOUT ))
while :; do
  remote=$(ssh "$SERVER" 'cd ~/pos-system && git rev-parse --short HEAD' 2>/dev/null)
  [ "$remote" = "$EXPECTED_COMMIT" ] && { log "server is at $remote"; break; }
  [ "$(date -u +%s)" -ge "$deadline" ] && die "server still at ${remote:-unknown} after ${DEPLOY_TIMEOUT}s"
  sleep 20
done

# --- verify by effect ------------------------------------------------------
log "=== VERIFY (by effect, not by exit code) ==="

log "-- alembic version --"
ssh "$SERVER" "docker exec pos-system-backend-1 alembic current 2>&1 | tail -2"

log "-- the new column, and the backfill --"
ssh "$SERVER" "docker exec pos-system-postgres-1 sh -c 'psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT intends_card_payment, (stripe_checkout_session_id IS NOT NULL) AS had_session, count(*) FROM orders GROUP BY 1,2 ORDER BY 1,2;\"'"

log "-- the fix, read out of the RUNNING container (not off disk) --"
ssh "$SERVER" "docker exec pos-system-backend-1 sh -c 'grep -c intends_card_payment app/services/order_visibility.py app/services/public_order_service.py app/models/order.py'"

log "-- containers, and Orbit CRM which must be untouched --"
ssh "$SERVER" "docker ps --format '{{.Names}}\t{{.Status}}' | sort"

log "-- public URLs --"
for url in https://eats.sitaratech.info/api/v1/health \
           https://eats.sitaratech.info/api/v1/public/chick-shack/menu \
           https://chickshackg84.com/ ; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -A "$UA" "$url")
  log "   $code  $url"
done

log "-- CORS on the real storefront origin --"
curl -s -D - -o /dev/null -A "$UA" -H "Origin: https://chickshackg84.com" \
  https://eats.sitaratech.info/api/v1/public/chick-shack/menu | grep -i '^access-control-allow-origin' || log "   NO ACAO HEADER"

log "-- backend exceptions and nginx 5xx since the deploy --"
ssh "$SERVER" "cd ~/pos-system && docker compose -f docker-compose.demo.yml --env-file .env.demo logs --since 10m backend 2>&1 | grep -ciE 'traceback|exception' || echo 0"

log "=== DONE. Read the output above before calling this deployed. ==="
log "Backup: $dump"
