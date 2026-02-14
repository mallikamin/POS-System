#!/usr/bin/env bash
# =============================================================================
# POS System — Demo Server Deployment Script
#
# Run this on a fresh Ubuntu 22.04/24.04 VPS (DigitalOcean, Hetzner, etc.)
#
# Prerequisites:
#   - SSH access to the server
#   - A domain name pointed to the server IP (optional, for SSL later)
#
# Usage:
#   1. SSH into your server
#   2. Clone the repo: git clone <your-repo-url> pos-system && cd pos-system
#   3. Run: bash scripts/deploy-demo.sh
#   4. The script will ask for your QuickBooks credentials
# =============================================================================
set -euo pipefail

echo "=============================================="
echo "  POS System — Demo Server Setup"
echo "=============================================="
echo ""

# ---------------------------------------------------
# Step 1: Install Docker (if not present)
# ---------------------------------------------------
if ! command -v docker &> /dev/null; then
    echo "==> Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "Docker installed. You may need to log out and back in for group changes."
fi

if ! docker compose version &> /dev/null; then
    echo "ERROR: docker compose not found. Please install Docker Compose v2."
    exit 1
fi

echo "==> Docker version: $(docker --version)"
echo ""

# ---------------------------------------------------
# Step 2: Collect environment variables
# ---------------------------------------------------
if [ ! -f .env.demo ]; then
    echo "==> Creating .env.demo — please provide the following values:"
    echo ""

    # Generate a secure secret key
    SECRET_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -hex 16)
    REDIS_PASSWORD=$(openssl rand -hex 16)

    read -rp "Server IP or domain (e.g., 123.45.67.89 or demo.yoursite.com): " SERVER_HOST
    read -rp "QB_CLIENT_ID (from Intuit Developer Portal): " QB_CLIENT_ID
    read -rp "QB_CLIENT_SECRET: " QB_CLIENT_SECRET
    read -rp "QB_ENVIRONMENT (sandbox/production) [sandbox]: " QB_ENV
    QB_ENV=${QB_ENV:-sandbox}

    cat > .env.demo <<EOF
# POS Demo Environment — Generated $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Server: ${SERVER_HOST}

SECRET_KEY=${SECRET_KEY}

# Database
POSTGRES_DB=pos_system
POSTGRES_USER=pos_admin
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# Redis
REDIS_PASSWORD=${REDIS_PASSWORD}

# CORS
CORS_ORIGINS=http://${SERVER_HOST},https://${SERVER_HOST}

# QuickBooks
QB_CLIENT_ID=${QB_CLIENT_ID}
QB_CLIENT_SECRET=${QB_CLIENT_SECRET}
QB_REDIRECT_URI=http://${SERVER_HOST}/api/v1/integrations/quickbooks/callback
QB_ENVIRONMENT=${QB_ENV}
EOF

    echo ""
    echo "==> .env.demo created successfully."
    echo ""
    echo "IMPORTANT: Update your Intuit Developer Portal!"
    echo "  Redirect URI: http://${SERVER_HOST}/api/v1/integrations/quickbooks/callback"
    echo "  Launch URL:   http://${SERVER_HOST}/admin/quickbooks"
    echo ""
else
    echo "==> Using existing .env.demo"
fi

# ---------------------------------------------------
# Step 3: Build and deploy
# ---------------------------------------------------
echo "==> Building Docker images (this may take 3-5 minutes on first run)..."
docker compose -f docker-compose.demo.yml --env-file .env.demo build

echo "==> Starting services..."
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d

echo "==> Waiting for services to become healthy..."
sleep 10

# Check health
for i in {1..30}; do
    if docker compose -f docker-compose.demo.yml exec -T backend curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "==> Backend is healthy!"
        break
    fi
    echo "  Waiting for backend... ($i/30)"
    sleep 5
done

# ---------------------------------------------------
# Step 4: Run seed data
# ---------------------------------------------------
echo ""
read -rp "Seed demo data? (y/n) [y]: " SEED_DATA
SEED_DATA=${SEED_DATA:-y}

if [[ "$SEED_DATA" == "y" ]]; then
    echo "==> Seeding demo data..."
    docker compose -f docker-compose.demo.yml exec -T backend python scripts/seed.py
    echo "==> Seed complete."
fi

# ---------------------------------------------------
# Step 5: Done!
# ---------------------------------------------------
SERVER_HOST=$(grep -oP 'Server: \K.*' .env.demo 2>/dev/null || echo "YOUR_SERVER_IP")

echo ""
echo "=============================================="
echo "  DEPLOYMENT COMPLETE"
echo "=============================================="
echo ""
echo "  POS App:      http://${SERVER_HOST}"
echo "  API Docs:     http://${SERVER_HOST}/api/docs"
echo "  QB Admin:     http://${SERVER_HOST}/admin/quickbooks"
echo ""
echo "  Login:"
echo "    Email:    admin@demo.com"
echo "    Password: admin123"
echo "    PIN:      1234"
echo ""
echo "  Intuit Developer Portal — update these:"
echo "    Redirect URI: http://${SERVER_HOST}/api/v1/integrations/quickbooks/callback"
echo ""
echo "  Commands:"
echo "    Logs:     docker compose -f docker-compose.demo.yml logs -f"
echo "    Stop:     docker compose -f docker-compose.demo.yml down"
echo "    Restart:  docker compose -f docker-compose.demo.yml restart"
echo ""
