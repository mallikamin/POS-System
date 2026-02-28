#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://pos-demo.duckdns.org}"
EMAIL="${EMAIL:-admin@demo.com}"
PASSWORD="${PASSWORD:-admin123}"
METHOD="GET"
PATH_ONLY="/api/v1/health"
BODY_JSON=""
SKIP_AUTH="0"
UA="Mozilla/5.0 (X11; Linux x86_64) UAT-Tester"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"; shift 2 ;;
    --email)
      EMAIL="$2"; shift 2 ;;
    --password)
      PASSWORD="$2"; shift 2 ;;
    --method)
      METHOD="$2"; shift 2 ;;
    --path)
      PATH_ONLY="$2"; shift 2 ;;
    --body)
      BODY_JSON="$2"; shift 2 ;;
    --skip-auth)
      SKIP_AUTH="1"; shift ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2 ;;
  esac
done

if [[ "${PATH_ONLY:0:1}" != "/" ]]; then
  PATH_ONLY="/$PATH_ONLY"
fi

URL="$BASE_URL$PATH_ONLY"
TOKEN=""

if [[ "$SKIP_AUTH" != "1" ]]; then
  LOGIN_PAYLOAD=$(printf '{"email":"%s","password":"%s"}' "$EMAIL" "$PASSWORD")
  LOGIN_JSON=$(curl -sS -A "$UA" -H "Content-Type: application/json" -H "Accept: application/json" \
    -X POST "$BASE_URL/api/v1/auth/login" -d "$LOGIN_PAYLOAD")

  TOKEN=$(printf '%s' "$LOGIN_JSON" | python -c 'import json,sys; data=json.load(sys.stdin); print(data.get("tokens",{}).get("access_token",""))')

  if [[ -z "$TOKEN" ]]; then
    echo "Login succeeded but access token was empty." >&2
    exit 1
  fi
fi

HEADERS=(-A "$UA" -H "Accept: application/json")
if [[ -n "$TOKEN" ]]; then
  HEADERS+=(-H "Authorization: Bearer $TOKEN")
fi

if [[ -n "$BODY_JSON" ]]; then
  curl -sS "${HEADERS[@]}" -H "Content-Type: application/json" -X "$METHOD" "$URL" -d "$BODY_JSON"
else
  curl -sS "${HEADERS[@]}" -X "$METHOD" "$URL"
fi

echo