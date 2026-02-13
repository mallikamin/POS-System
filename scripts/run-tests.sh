#!/usr/bin/env bash
# =============================================================================
# POS System - Test Runner
# =============================================================================
# Runs the test suite inside Docker with isolated postgres and redis instances.
# Usage: bash scripts/run-tests.sh
# =============================================================================

set -euo pipefail

echo ""
echo "========================================="
echo "  POS System - Running Tests"
echo "========================================="
echo ""

# Run tests using the test compose override
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm test
EXIT_CODE=$?

# Clean up test containers
docker compose -f docker-compose.yml -f docker-compose.test.yml down

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "All tests passed."
else
    echo "Tests failed with exit code: $EXIT_CODE"
fi

exit $EXIT_CODE
