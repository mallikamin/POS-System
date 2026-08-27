# Deployment playbook

**The authoritative "how we ship" for this repo.** Short on purpose — if it is long,
nobody reads it at 23:00 with a client waiting.

`docs/DEPLOYMENT_CHECKLIST.md` remains the long-form reference for **manual** SSH
deploys and emergency recovery. This file covers the path we actually use.

---

## The one-line summary

⚠️ **There are TWO separate deploy pipelines. Read both before you push or run anything.**

| Changed... | Deploy command | Ships to |
|---|---|---|
| `backend/`, `frontend/` (POS admin/KDS), anything else at repo root | `git push origin main` | DigitalOcean droplet, via `deploy-production.yml` |
| `storefront/` (the Chick Shack customer-facing site) | `cd storefront && npm run deploy` | Cloudflare Workers — **`git push` does NOT touch this** |

**Merging to `main` deploys the POS/backend side only.** There is no other button *for that
side*. Do not SSH in and `git pull` by hand — that leaves the server on a commit no workflow
knows about. But a green `git push` / green Action tells you **nothing** about whether the
storefront changed — verify by fetching the live bundle and grepping for what you just edited,
not by trusting CI status. (This is exactly how a testing-mode banner shipped to `main` on
2026-07-30 sat un-deployed on the live site for several minutes while a GitHub Action ran green
for an unrelated pipeline — see `ERROR_LOG.md`.)

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

**1. nginx used to cache upstream IPs at startup.** (Fixed 2026-08-27, OI-92 item 1.)
Every `proxy_pass` now goes through a variable with `resolver 127.0.0.11`, so a replaced
`backend` is picked up per request. **An app deploy does not touch nginx at all any more.**
The one thing a reload still cannot do is pick up a *pulled* `nginx.demo.conf`: the config
is a single-file bind mount and `git pull` replaces the inode, so the running container
keeps the old content (measured on the box). `deploy-remote.sh` compares the md5 the
container sees with the file on disk and recreates nginx **only** when they differ.

**2. nginx must never be recreated without its mounts.**
All **five** are declared in `docker-compose.demo.yml`, so compose recreation is safe:
`nginx.demo.conf`, `voice.conf` (Orbit's), `certbot_certs`, `certbot_webroot`, and
`/root/pos-system/www` (the frontend releases). The script re-checks all five after any
recreate and aborts if one is missing.
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
2. `rsync`s `dist/` to `www/releases/<commit sha>/` (never `--delete`; it wiped the
   server once). Nothing serves it yet.
3. `git pull` on the server, and refuses if HEAD is not the commit the build is for.
4. Rebuilds and recreates `backend`, waits for healthy. **This is the only step a user
   can notice** — a few seconds of `/api/` 502s. OI-92 item 3 is the fix.
5. **`pg_dump` backup, and aborts if the dump is empty** — an unusable backup is worse
   than a missing one, because it gets trusted.
6. `alembic upgrade head`.
7. Points `www/current` at the new release with an **atomic symlink swap** (`mv -T`,
   never `ln -sfn`). nginx serves it directly; no container is involved. Keeps the 5
   newest releases, so a rollback is `ln -s releases/<old> .tmp && mv -T .tmp current`.
8. Asserts `voice.conf` exists. nginx is **left alone** unless `nginx.demo.conf` changed,
   in which case the new config is `nginx -t`'d in a throwaway container first, then
   nginx is recreated (every hostname blips for a few seconds; time it accordingly).
9. Verifies **every hostname**: HTTP status, that each serves **its own certificate**,
   that the live `index.html` references a chunk from **this** build, and that the
   bundle arrives **gzipped**.

Step 9's certificate check exists because `eats.sitaratech.info` served the wrong cert
for two weeks and nothing noticed until a human opened a browser. The build check exists
because an edit to a file nginx never loaded looked like a shipped feature for months.

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
