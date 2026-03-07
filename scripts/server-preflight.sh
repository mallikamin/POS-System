#!/usr/bin/env bash
set -euo pipefail

# Source of truth
SERVER_DOC="SERVER.md"
EXPECTED_HOST="pos-demo.duckdns.org"
EXPECTED_PATH="~/pos-system"

if [[ ! -f "$SERVER_DOC" ]]; then
  echo "ERROR: ${SERVER_DOC} not found. Cannot validate server details."
  exit 1
fi

DOC_IP="$(grep -E '^\| IP \|' "$SERVER_DOC" | sed -E 's/^\| IP \|[[:space:]]*([^|]+)[[:space:]]*\|/\1/' | tr -d '[:space:]')"

if [[ -z "${DOC_IP}" ]]; then
  echo "ERROR: Could not parse IP from ${SERVER_DOC}."
  exit 1
fi

if command -v nslookup >/dev/null 2>&1; then
  DNS_IPS="$(nslookup "$EXPECTED_HOST" 2>/dev/null | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' | tr '\n' ' ')"
elif command -v dig >/dev/null 2>&1; then
  DNS_IPS="$(dig +short "$EXPECTED_HOST" A | tr '\n' ' ')"
else
  DNS_IPS=""
fi

echo "Server preflight"
echo "  Host (canonical): ${EXPECTED_HOST}"
echo "  IP (SERVER.md):   ${DOC_IP}"
echo "  Project path:     ${EXPECTED_PATH}"

if [[ -n "${DNS_IPS}" ]]; then
  echo "  DNS resolves to:  ${DNS_IPS}"
  if [[ "${DNS_IPS}" != *"${DOC_IP}"* ]]; then
    echo "ERROR: DNS does not include SERVER.md IP (${DOC_IP}). Stop and verify droplet/IP first."
    exit 1
  fi
else
  echo "  DNS check:        skipped (nslookup/dig not available)"
fi

echo ""
echo "Use only this SSH target:"
echo "  ssh root@${DOC_IP}"
echo ""
echo "Then confirm server path:"
echo "  cd ${EXPECTED_PATH} && pwd"
echo ""
echo "Preflight passed."
