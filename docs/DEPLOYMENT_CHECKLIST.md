# Deployment Checklist - pos-demo.duckdns.org

**Use this checklist for EVERY deployment to production/demo environment.**

---

## Pre-Deployment (MUST DO BEFORE ANY CHANGES)

### 1. Backup Current State ⚠️ CRITICAL
```bash
# Backup database
ssh root@159.65.158.26 "cd ~/pos-system && docker compose exec -T postgres \
  pg_dump -U pos_admin pos_system | gzip > ~/backups/pos-$(date +%Y%m%d-%H%M%S).sql.gz"

# Backup .env.demo file
ssh root@159.65.158.26 "cd ~/pos-system && \
  tar -czf ~/backups/env-$(date +%Y%m%d-%H%M%S).tar.gz .env.demo"

# Verify backups created
ssh root@159.65.158.26 "ls -lh ~/backups/ | tail -5"
```

### 2. Document What You're Deploying
```bash
# Create deployment log
cat > logs/deployments/$(date +%Y-%m-%d_%H-%M)_<description>.md << 'EOF'
# Deployment: <Brief Description>
**Date:** $(date)
**Git Hash (before):** $(git rev-parse HEAD)
**Triggered by:** <Your Name>

## Changes Being Deployed
- <List commits or features>

## Expected Impact
- <What will change>

## Rollback Plan
- <How to revert if it fails>
EOF
```

### 3. Check Environment File Exists
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  [ -f .env.demo ] && echo '✅ .env.demo exists' || echo '❌ .env.demo MISSING!'"
```

### 4. Check SSL Certificates Valid
```bash
ssh root@159.65.158.26 "certbot certificates | grep pos-demo"
```

### 5. Check Current System Health
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo ps"

# All containers should show "healthy" status
```

---

## Deployment Steps

### 1. Pull Latest Code
```bash
ssh root@159.65.158.26 "cd ~/pos-system && git pull origin main"
```

### 2. Check for Database Migrations
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend \
  alembic current"
```

### 3. Run Migrations (if any)
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend \
  alembic upgrade head"
```

### 4. Rebuild & Restart Services
**If code changed:**
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build"
```

**If ONLY env vars changed:**
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --no-deps backend"
```

### 5. Watch Logs During Startup
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f backend"

# Watch for errors, wait for "Application startup complete"
# Press Ctrl+C to exit logs
```

---

## Post-Deployment Validation

### 1. Check Container Health (CRITICAL)
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo ps"
```

**Expected Output:**
```
All containers should show:
- STATUS: Up X minutes (healthy)
- No "Restarting" or "unhealthy" statuses
```

**If any container unhealthy:**
```bash
# Check logs
docker compose logs <service-name> --tail 50

# Common fixes:
# - Backend: Check database connection, env vars
# - Nginx: Check SSL certificates, upstream backend
# - Postgres: Check password, volume permissions
# - Redis: Check password match
```

### 2. Test Health Endpoint
```bash
curl -s https://pos-demo.duckdns.org/api/v1/health | jq .
```

**Expected Output:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

**If "degraded":**
- Check which service is unhealthy
- Check logs for that service
- Verify credentials in .env.demo

### 3. Test Login (Smoke Test)
```bash
# Test PIN login
curl -X POST https://pos-demo.duckdns.org/api/v1/auth/login/pin \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}' | jq .

# Should return: {"access_token": "...", "token_type": "bearer", ...}
```

**If 400 Bad Request:**
- Database might be empty → run seed script
- Credentials wrong → check env vars

### 4. Test Critical Flows
Open browser and manually test:

- [ ] Login with admin@demo.com / admin123
- [ ] Navigate to Dashboard
- [ ] Navigate to Dine-In → Table selection works
- [ ] Navigate to Admin → Menu loads
- [ ] Navigate to Admin → QuickBooks page loads
- [ ] WebSocket connection works (check browser console)

### 5. Check Nginx Access Logs
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose logs nginx --tail 20"

# Should see successful requests (200 OK)
# No 502 Bad Gateway or 444 errors
```

---

## Rollback Procedure (If Deployment Fails)

### Option 1: Rollback Code
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  git reset --hard <previous-commit-hash> && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build"
```

### Option 2: Restore Database Backup
```bash
# Stop services
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml down"

# Restore database
ssh root@159.65.158.26 "gunzip < ~/backups/pos-YYYYMMDD-HHMMSS.sql.gz | \
  docker compose exec -T postgres psql -U pos_admin -d pos_system"

# Restart
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose -f docker-compose.demo.yml --env-file .env.demo up -d"
```

### Option 3: Full System Restore (LAST RESORT)
```bash
# Restore env file
ssh root@159.65.158.26 "cd ~/pos-system && \
  tar -xzf ~/backups/env-YYYYMMDD-HHMMSS.tar.gz"

# Restore database
ssh root@159.65.158.26 "cd ~/pos-system && \
  docker compose down -v && \
  docker compose up -d postgres && \
  sleep 10 && \
  gunzip < ~/backups/pos-YYYYMMDD-HHMMSS.sql.gz | \
  docker compose exec -T postgres psql -U pos_admin -d pos_system && \
  docker compose up -d"
```

---

## Common Issues & Quick Fixes

### Issue 1: Backend Unhealthy
**Symptoms:** Backend container keeps restarting, health check fails

**Check:**
```bash
docker compose logs backend --tail 50
```

**Common Causes:**
- Database connection failed → Check POSTGRES_PASSWORD in .env.demo
- Redis connection failed → Check REDIS_PASSWORD matches redis.conf
- Missing env var → Check all required vars in .env.demo
- Import error → Check all dependencies in requirements.txt

**Quick Fix:**
```bash
# Restart backend
docker compose up -d --no-deps backend

# If still failing, rebuild
docker compose up -d --build --no-deps backend
```

### Issue 2: Nginx 502 Bad Gateway
**Symptoms:** Frontend loads but API calls return 502

**Cause:** Backend not ready or crashed

**Fix:**
```bash
# Check backend health
docker compose exec nginx wget -qO- http://backend:8000/api/v1/health

# Restart nginx
docker compose restart nginx
```

### Issue 3: SSL Certificate Error
**Symptoms:** Nginx won't start, "cannot load certificate" error

**Fix:**
```bash
# Copy certs from host to volume
docker run --rm \
  -v pos-system_certbot_certs:/certs \
  -v /etc/letsencrypt:/host-certs \
  alpine sh -c 'cp -r /host-certs/* /certs/'

# Restart nginx
docker compose restart nginx
```

### Issue 4: Database Empty After Deploy
**Symptoms:** Login returns 400, no users exist

**Fix:**
```bash
# Run seed script
docker compose exec backend python -m app.scripts.seed
```

### Issue 5: WebSocket Not Working
**Symptoms:** KDS not updating in real-time, no WS connection in browser console

**Check:**
```bash
# Check redis healthy
docker compose ps redis

# Check backend logs for WS errors
docker compose logs backend | grep -i websocket
```

**Fix:**
```bash
# Restart backend
docker compose restart backend
```

---

## Environment Variables Checklist

**CRITICAL - These MUST be set in .env.demo:**

```bash
# Application
✓ SECRET_KEY (64+ char random string)
✓ ENVIRONMENT=staging
✓ DEBUG=false

# Database
✓ POSTGRES_DB=pos_system
✓ POSTGRES_USER=pos_admin
✓ POSTGRES_PASSWORD (strong password)

# Redis
✓ REDIS_PASSWORD (must match redis.conf)

# CORS
✓ CORS_ORIGINS=https://pos-demo.duckdns.org

# QuickBooks
✓ QB_CLIENT_ID (from Intuit developer portal)
✓ QB_CLIENT_SECRET (from Intuit developer portal)
✓ QB_REDIRECT_URI=https://pos-demo.duckdns.org/api/v1/integrations/quickbooks/callback
✓ QB_ENVIRONMENT=sandbox
```

**To verify all vars set:**
```bash
ssh root@159.65.158.26 "cd ~/pos-system && \
  grep -E '^[A-Z_]+=' .env.demo | grep -v '^#' | wc -l"

# Should be 10+ vars
```

---

## Emergency Contacts

| Issue | Contact | Action |
|-------|---------|--------|
| Server down | DigitalOcean Support | Check droplet status, restart if needed |
| SSL expired | Run certbot | `certbot renew --force-renewal` |
| Database corrupted | Restore from backup | Follow rollback procedure |
| Code bug | Revert commit | `git revert <hash>` and redeploy |
| QB OAuth broken | Reconnect | Admin → QuickBooks → Disconnect → Connect |

---

## Post-Deployment Documentation

**After successful deployment, document in git:**

```bash
cd logs/deployments
# Edit the deployment log created earlier
# Add final status, any issues encountered, resolution

git add logs/deployments/
git commit -m "Deploy log: <description>"
git push origin main
```

**Update MEMORY.md if needed:**
- New learnings
- New known issues
- Configuration changes
- Breaking changes

---

## Weekly Maintenance Checklist

**Run every Monday:**

- [ ] Check all backups exist and are recent
- [ ] Check SSL certificate expiry (`certbot certificates`)
- [ ] Check disk space (`df -h`)
- [ ] Check Docker image updates (`docker images`)
- [ ] Review logs for errors (`docker compose logs --tail 1000 | grep ERROR`)
- [ ] Test backup restore (monthly)
- [ ] Update dependencies if needed

---

## Deployment Sign-off

**Before closing deployment:**

- [ ] All containers healthy
- [ ] Health endpoint returns "healthy"
- [ ] Login works
- [ ] Critical flows tested
- [ ] No errors in logs
- [ ] Deployment documented
- [ ] Team notified

**Deployment completed by:** _______________
**Date:** _______________
**Status:** ✅ Success / ❌ Failed / ⚠️ Partial
