# Deployment playbook

**The authoritative "how we ship" for this repo.** Short on purpose — if it is long,
nobody reads it at 23:00 with a client waiting.

`docs/DEPLOYMENT_CHECKLIST.md` remains the long-form reference for **manual** SSH
deploys and emergency recovery. This file covers the path we actually use.

---

## The one-line summary

**Merging to `main` deploys production.** There is no other button. Do not SSH in and
`git pull` by hand — that leaves the server on a commit no workflow knows about.

---

## What the box actually is

One 2GB DigitalOcean droplet (`159.65.158.26`, SGP1) running **two unrelated projects
behind one shared nginx**:

| Container | Project |
|---|---|
| `pos-system-{nginx,frontend,backend,postgres,redis}` | POS |
| `orbit_{api,db,web}` | Orbit CRM — **not ours** |

Hostnames served: `pos-demo.duckdns.org`, `eats.sitaratech.info` (**the client's tablet**),
`orbit-voice.duckdns.org`, `parkcity.sitaratech.info`.

**nginx is shared infrastructure.** Breaking it takes down someone else's business, and
has, twice.

---

## The three rules that have actually bitten us

**1. nginx caches upstream IPs at startup.**
Recreating `frontend`/`backend` gives them new IPs. nginx keeps using the old ones and
returns **502**. `restart` does *not* fix it — only a new container does. This is why
every past deploy ended with a hand-fixed 502.
→ The workflow now recreates nginx **last**, automatically.

**2. nginx must never be recreated without its mounts.**
All four are declared in `docker-compose.demo.yml`, so compose recreation is safe:
`nginx.demo.conf`, `voice.conf` (Orbit's), `certbot_certs`, `certbot_webroot`.
⚠️ If `/root/orbit-crm/voice.conf` is missing from the **host**, Docker creates a
*directory* there and nginx refuses to start — taking **both** sites down.
→ The workflow asserts that file exists and **aborts** rather than risking it.

**3. The server returns 444 to `curl`.**
`nginx.demo.conf` blocks bad-bot user agents at *server* level, above every location
including `/api/`. Pattern matches `curl/`, `wget/`, `python-requests`.
→ Always pass `-A "Mozilla/5.0 ..."`. A 444 is the bot filter, not an outage. **Stop
debugging it.**

---

## Deploying

```
git push origin main        # this IS the deploy
```

`deploy-production.yml` then, in order:

1. Builds the frontend **on the GitHub runner** — never on the box (2GB RAM will OOM).
2. `rsync`s `dist/` (never `--delete`; it wiped the server once).
3. `git pull` on the server, builds frontend via `Dockerfile.prebuilt`, recreates it.
4. Rebuilds and recreates `backend`.
5. **`pg_dump` backup, and aborts if the dump is empty** — an unusable backup is worse
   than a missing one, because it gets trusted.
6. `alembic upgrade head`.
7. Asserts `voice.conf` exists → recreates **nginx** → `nginx -t`.
8. Verifies **every hostname**: HTTP status *and* that each serves **its own certificate**.

Step 8's certificate check exists because `eats.sitaratech.info` served the wrong cert
for two weeks and nothing noticed until a human opened a browser.

⚠️ Pushing to `main` also triggers `deploy-staging.yml`, which targets **AWS ECS**
(`me-south-1`) and is expected to fail on credentials. It cannot touch this droplet.
Ignore it, or delete the workflow.

---

## Deploying the storefront (separate, and it is a business event)

```
cd storefront && npm run deploy     # vite build + wrangler deploy
```

Goes to Cloudflare Workers, **not** the droplet. Nothing above applies.

🔺 **This is the UAT trigger, not a build step.** The moment it lands, `chickshackg84.com`
takes real orders from real customers and every one goes to Imran's tablet. Run it only
when he is at the tablet and expecting it. Time it with him.

---

## Before you touch the server by hand

Read `memory/server-deployment-rules.md` (in the Claude project memory dir, not the repo)
and `memory/data-integrity.md` — **`pg_dump` first, no exceptions.**

Read-only audit that is always safe:

```bash
ssh root@159.65.158.26 'docker ps -a'
docker inspect pos-system-nginx-1 --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}"
```

**Never `git add .` in this repo** — `.env.demo` is tracked and carries live credentials.

---

## If it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| 502 on any hostname | nginx cached the old upstream IP | Recreate nginx (mounts are in compose) |
| 444 from a script | Bot filter matched your UA | Add a browser `-A`. Not an outage |
| `ERR_CERT_COMMON_NAME_INVALID` on orbit-voice | `voice.conf` not mounted | Check the host file, recreate nginx |
| Migration failed | — | Restore the `backups/pre_migrate_*.sql` the deploy just took |
| Frontend build OOM | Built on the box | Never do that. Let CI build it |
