# Server Reference — POS System

## Server Details
| Field | Value |
|-------|-------|
| Provider | DigitalOcean |
| IP | 159.65.158.26 |
| Region | SGP1 (Singapore) |
| Spec | 2GB RAM, 1 vCPU, 50GB SSD |
| Cost | $12/month |
| OS | Ubuntu 24.04 LTS |
| Domain | pos-demo.duckdns.org |
| SSL | Let's Encrypt (certbot) |
| DNS | DuckDNS (free) |

## SSH Access
```bash
ssh root@159.65.158.26
```

## Project Location on Server
```
~/pos-system/
```

## Quick Commands

### Start / Restart Everything
```bash
cd ~/pos-system
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d
```

### Stop Everything
```bash
cd ~/pos-system
docker compose -f docker-compose.demo.yml --env-file .env.demo down
```

### View Logs
```bash
# All services
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f

# Specific service
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f backend
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f nginx
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f frontend
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f postgres
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f redis
```

### Check Service Status
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo ps
```

### Pull Latest Code & Rebuild
```bash
cd ~/pos-system
git pull
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build
```

### Rebuild Single Service (no downtime for others)
```bash
# Frontend only
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build frontend

# Backend only (no rebuild needed if only env changes)
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --no-deps backend
```

### Run Database Migrations
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend alembic upgrade head
```

### Run Seed Script
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend python -m app.scripts.seed
```

### Access PostgreSQL Shell
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec postgres psql -U pos_admin -d pos_system
```

### Access Redis CLI
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec redis redis-cli
```

### Edit Environment Variables
```bash
nano ~/pos-system/.env.demo
```

## .env.demo Template
```
SECRET_KEY=<random-secret>
POSTGRES_USER=pos_admin
POSTGRES_PASSWORD=<db-password>
POSTGRES_DB=pos_system
REDIS_PASSWORD=<redis-password>
CORS_ORIGINS=https://pos-demo.duckdns.org
QB_CLIENT_ID=<from-intuit-portal>
QB_CLIENT_SECRET=<from-intuit-portal>
QB_REDIRECT_URI=https://pos-demo.duckdns.org/api/v1/integrations/quickbooks/callback
QB_ENVIRONMENT=sandbox
```

To switch to production QuickBooks:
```
QB_CLIENT_ID=<production-client-id>
QB_CLIENT_SECRET=<production-client-secret>
QB_ENVIRONMENT=production
```

## SSL Certificate Renewal (every 90 days)
```bash
cd ~/pos-system
docker compose -f docker-compose.demo.yml --env-file .env.demo stop nginx
certbot renew
docker run --rm -v pos-system_certbot_certs:/certs -v /etc/letsencrypt:/host-certs:ro alpine sh -c "cp -rL /host-certs/* /certs/"
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d
```

## DuckDNS
- Manage at: https://www.duckdns.org
- Account: mallikamin@github
- Subdomain: pos-demo
- If server IP changes: update on DuckDNS website
- Token is only for DNS management — not used in any code

## Login Credentials (after seed)
| User | Email | Password | PIN | Role |
|------|-------|----------|-----|------|
| Admin | admin@demo.com | admin123 | 1234 | admin |
| Cashier | cashier@demo.com | cashier123 | 5678 | cashier |
| Kitchen | kitchen@demo.com | kitchen123 | 9012 | kitchen |
| Younis Kamran | youniskamran@demo.com | yk123 | 1111 | admin |

## URLs
| Page | URL |
|------|-----|
| App | https://pos-demo.duckdns.org |
| API Docs | https://pos-demo.duckdns.org/api/docs |
| API Health | https://pos-demo.duckdns.org/api/v1/health |
| Privacy Policy | https://pos-demo.duckdns.org/privacy.html |
| EULA | https://pos-demo.duckdns.org/eula.html |

## Intuit Developer Portal
- URL: https://developer.intuit.com
- Development redirect URI: https://pos-demo.duckdns.org/api/v1/integrations/quickbooks/callback
- Production redirect URI: https://pos-demo.duckdns.org/api/v1/integrations/quickbooks/callback
- App categories: Accounting, Sales, Income Management, Inventory Management
- Assessment status: APPROVED

## Troubleshooting

### Containers not starting
```bash
# Check what's failing
docker compose -f docker-compose.demo.yml --env-file .env.demo ps
docker compose -f docker-compose.demo.yml --env-file .env.demo logs --tail 50 <service-name>
```

### env var warnings (harmless)
If you see `WARN: The "SECRET_KEY" variable is not set`, you forgot `--env-file .env.demo`.

### Backend health check failing
```bash
# Check backend logs
docker compose -f docker-compose.demo.yml --env-file .env.demo logs --tail 100 backend
# Common cause: database not ready yet — wait for postgres healthcheck
```

### Seed script ModuleNotFoundError
Always run as `python -m app.scripts.seed`, never `python app/scripts/seed.py`.

### nginx SSL errors after cert renewal
Make sure you copy certs to Docker volume after renewal (see SSL section above).
