# TARS Server Commands

## Connect to Server
```bash
ssh root@159.65.158.26
cd ~/pos-system
```

## Start All Services
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d
```

## Stop All Services
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo down
```

## Restart All Services
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo restart
```

## Check Status
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo ps
```

## View Logs
```bash
# All
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f
# Backend only
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f backend
# Nginx only
docker compose -f docker-compose.demo.yml --env-file .env.demo logs -f nginx
```

## Deploy Code Updates
```bash
cd ~/pos-system
git pull
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build
```

## Rebuild Single Service
```bash
# Frontend
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build frontend
# Backend
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --build backend
# Backend (env change only, no rebuild)
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --no-deps backend
```

## Database

### Run Migrations
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend alembic upgrade head
```

### Run Seed Script
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend python -m app.scripts.seed
```

### Open PostgreSQL Shell
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec postgres psql -U pos_admin -d pos_system
```

### Quick SQL Query
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec postgres psql -U pos_admin -d pos_system -c "YOUR SQL HERE;"
```

## Create New User (without rebuilding)

### Step 1: Generate password hash
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend python -c "from app.utils.security import hash_password; print(hash_password('THE_PASSWORD'))"
```

### Step 2: Generate PIN hash
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec backend python -c "from app.utils.security import hash_password; print(hash_password('THE_PIN'))"
```

### Step 3: Insert via SQL (replace HASH_PW, HASH_PIN, email, name, role)
```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo exec postgres psql -U pos_admin -d pos_system -c "INSERT INTO users (id, tenant_id, email, full_name, hashed_password, pin_code, role_id, is_active, created_at, updated_at) SELECT gen_random_uuid(), t.id, 'EMAIL', 'FULL_NAME', 'HASH_PW', 'HASH_PIN', r.id, true, now(), now() FROM tenants t, roles r WHERE r.name = 'ROLE' AND r.tenant_id = t.id LIMIT 1;"
```
Roles: `admin`, `cashier`, `kitchen`

## Edit Environment Variables
```bash
nano ~/pos-system/.env.demo
# Save: Ctrl+O → Enter → Ctrl+X
```

## Switch QuickBooks Mode

### To Production
```
QB_CLIENT_ID=<production ID>
QB_CLIENT_SECRET=<production secret>
QB_ENVIRONMENT=production
```

### To Sandbox
```
QB_CLIENT_ID=<sandbox ID>
QB_CLIENT_SECRET=<sandbox secret>
QB_ENVIRONMENT=sandbox
```
After editing, restart backend: `docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --no-deps backend`

## SSL Certificate Renewal (every 90 days)
```bash
cd ~/pos-system
docker compose -f docker-compose.demo.yml --env-file .env.demo stop nginx
certbot renew
docker run --rm -v pos-system_certbot_certs:/certs -v /etc/letsencrypt:/host-certs:ro alpine sh -c "cp -rL /host-certs/* /certs/"
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d
```

## URLs
| Page | URL |
|------|-----|
| App | https://pos-demo.duckdns.org |
| API Docs | https://pos-demo.duckdns.org/api/docs |
| Health Check | https://pos-demo.duckdns.org/api/v1/health |

## Login Credentials
| User | Email | Password | PIN | Role |
|------|-------|----------|-----|------|
| Admin | admin@demo.com | admin123 | 1234 | admin |
| Cashier | cashier@demo.com | cashier123 | 5678 | cashier |
| Kitchen | kitchen@demo.com | kitchen123 | 9012 | kitchen |
| Younis Kamran | youniskamran@demo.com | yk123 | 1111 | admin |
