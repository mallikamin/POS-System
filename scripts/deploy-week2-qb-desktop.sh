#!/bin/bash
# Deploy QB Desktop Week 2 + Fix .env.demo
# Run this on the server: bash scripts/deploy-week2-qb-desktop.sh

set -e  # Exit on error

echo "======================================"
echo "QB Desktop Week 2 Deployment"
echo "======================================"
echo ""

# Change to project directory
cd ~/pos-system

# Verify .env.demo exists
if [ ! -f .env.demo ]; then
    echo "❌ ERROR: .env.demo not found!"
    echo "Please upload .env.demo first using:"
    echo "  scp .env.demo root@159.65.158.26:~/pos-system/"
    exit 1
fi

echo "✅ .env.demo found"
echo ""

# Pull latest code (includes Week 2 commits: ebfb9ed, 464f69c)
echo "📥 Pulling latest code from GitHub..."
git fetch origin main
git pull origin main
echo ""

# Show recent commits
echo "📝 Recent commits:"
git log --oneline -5
echo ""

# Stop services
echo "🛑 Stopping services..."
docker compose -f docker-compose.demo.yml --env-file .env.demo down
echo ""

# Rebuild backend (includes QB Desktop code)
echo "🔨 Building backend with QB Desktop Week 2 code..."
docker compose -f docker-compose.demo.yml --env-file .env.demo build backend
echo ""

# Start all services
echo "🚀 Starting all services..."
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d
echo ""

# Wait for services to start
echo "⏳ Waiting 10 seconds for services to initialize..."
sleep 10
echo ""

# Check service status
echo "📊 Service Status:"
docker compose -f docker-compose.demo.yml ps
echo ""

# Check backend logs
echo "📋 Backend Logs (last 30 lines):"
docker compose -f docker-compose.demo.yml logs backend --tail 30
echo ""

# Test endpoints
echo "🧪 Testing Endpoints:"
echo ""
echo "1. Health Check:"
curl -s https://pos-demo.duckdns.org/api/v1/health | jq . || echo "❌ Health check failed"
echo ""

echo "2. QBWC Endpoint (should return SOAP error for GET):"
curl -s https://pos-demo.duckdns.org/api/v1/qbwc/ | head -5
echo ""

# Summary
echo ""
echo "======================================"
echo "✅ Deployment Complete!"
echo "======================================"
echo ""
echo "Services:"
echo "  - POS: https://pos-demo.duckdns.org"
echo "  - API Docs: https://pos-demo.duckdns.org/api/docs"
echo "  - QBWC SOAP: https://pos-demo.duckdns.org/api/v1/qbwc/"
echo ""
echo "QB Desktop Features:"
echo "  ✅ 7 QBXML Builders (Sales Receipt, Customer, Item, Payment, Refund)"
echo "  ✅ Desktop Adapter (async queue-based sync)"
echo "  ✅ Adapter Factory (auto-detect Online vs Desktop)"
echo "  ✅ QBWC SOAP Server (Week 1)"
echo ""
echo "Next Steps:"
echo "  1. Download QBWC: https://qbwc.qbn.intuit.com/"
echo "  2. Generate QWC file from POS admin"
echo "  3. Import QWC into QBWC client"
echo "  4. Test sync flow"
echo ""
