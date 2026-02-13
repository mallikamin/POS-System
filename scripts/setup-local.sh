#!/usr/bin/env bash
# =============================================================================
# POS System - Local Development Setup
# =============================================================================
# One-command setup for new developers.
# Usage: bash scripts/setup-local.sh
# =============================================================================

set -euo pipefail

# -- Colors -------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERR]${NC}  $1"; exit 1; }

echo ""
echo "========================================="
echo "  POS System - Local Setup"
echo "========================================="
echo ""

# -- Step 1: Check prerequisites ---------------------------------------------
info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please install Docker Desktop: https://docs.docker.com/get-docker/"
fi
success "Docker found: $(docker --version)"

if ! docker compose version &> /dev/null; then
    error "Docker Compose V2 is not available. Please update Docker Desktop."
fi
success "Docker Compose found: $(docker compose version --short)"

if ! command -v git &> /dev/null; then
    error "Git is not installed. Please install Git: https://git-scm.com/"
fi
success "Git found: $(git --version)"

if ! docker info &> /dev/null 2>&1; then
    error "Docker daemon is not running. Please start Docker Desktop."
fi
success "Docker daemon is running"

echo ""

# -- Step 2: Environment file ------------------------------------------------
info "Setting up environment file..."

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        success "Created .env from .env.example"
        warn "Review .env and update SECRET_KEY before deploying to any non-local environment."
    else
        error ".env.example not found. Are you in the project root directory?"
    fi
else
    success ".env already exists, skipping copy"
fi

echo ""

# -- Step 3: Build and start services ----------------------------------------
info "Building and starting all services..."
docker compose up --build -d

echo ""

# -- Step 4: Wait for services to become healthy ------------------------------
info "Waiting for services to become healthy..."

MAX_WAIT=120
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
    BACKEND_HEALTH=$(docker compose ps --format json backend 2>/dev/null | grep -o '"Health":"[^"]*"' | head -1 || echo "")

    if echo "$BACKEND_HEALTH" | grep -q "healthy"; then
        success "Backend is healthy"
        break
    fi

    echo -n "."
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    warn "Backend did not become healthy within ${MAX_WAIT}s. Check logs with: docker compose logs backend"
fi

# Check individual services
echo ""
info "Service status:"
docker compose ps

echo ""
echo "========================================="
echo "  Setup Complete"
echo "========================================="
echo ""
echo "  Application:   http://localhost"
echo "  API Docs:      http://localhost/api/v1/docs"
echo "  PostgreSQL:    localhost:5432"
echo "  Redis:         localhost:6379"
echo ""
echo "  Useful commands:"
echo "    make logs          - Tail all service logs"
echo "    make logs-backend  - Tail backend logs"
echo "    make psql          - Open database shell"
echo "    make test          - Run test suite"
echo "    make down          - Stop all services"
echo ""
