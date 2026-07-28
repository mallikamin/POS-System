# Infrastructure state — servers, domains, DNS, deploys

**Last updated:** 2026-07-27 (04:12 PKT / 2026-07-26 23:12 UTC)

⚠️ **`memory/server-deployment-rules.md` is a mandatory read before ANY server operation.** This file
is the current picture; that one is the protocol. Credentials are in
`INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` and `_context/secrets/` — **reference by path, never echo
values.**

---

## Where things run

| Thing | Runs on | Status |
|---|---|---|
| Chick Shack storefront | **Cloudflare Workers** (static assets), project `chick-shack-storefront` | ✅ Live |
| POS app + API | DigitalOcean droplet **159.65.158.26** (SGP1), `~/pos-system` | ✅ Live |
| **POS — client-facing** | **`eats.sitaratech.info`** | ✅ **This is the domain to give a client.** Own SSL cert since 2026-07-28 |
| POS demo (legacy) | `pos-demo.duckdns.org` | ✅ Green. Same application, kept working — but do not hand a duckdns URL to a paying client |
| Orbit CRM voice | `orbit-voice.duckdns.org` | Shares this server |
&nbsp;

> ⚠️ **2026-07-28 — `eats.sitaratech.info` was half-migrated for two weeks.**
> The 2026-07-15 change added it to nginx `server_name` but **never issued a certificate**,
> and it resolves straight to the origin with no Cloudflare in front. Both names shared one
> 443 block, and a block can only present one certificate — so every visitor to
> `https://eats.sitaratech.info` got the `pos-demo` certificate and an
> `ERR_CERT_COMMON_NAME_INVALID` refusal. The same failure as the March orbit-voice incident.
>
> Fixed by issuing its own certificate and splitting it into its own server block
> (`nginx.demo.conf`, reload only — no container recreation). Verified per-hostname with
> `openssl s_client -servername`: all three now serve their own certificate.
>
> **Lesson: adding a hostname to `server_name` is half a migration.** The certificate is the
> other half, and nothing fails until a human opens a browser.
| Orbit CRM parkcity | `parkcity.sitaratech.info` | Shares this server |

### ⚠️ The DigitalOcean box is shared infrastructure

**Three separate projects sit behind one nginx.** This has already caused one outage: recreating
nginx without checking volume mounts took `orbit-voice.duckdns.org` down for ~20 minutes on
2026-03-26. Before any container operation: `docker ps -a` to see every project, and
`docker inspect pos-system-nginx-1` to check **all** volume mounts.

Other standing constraints on this box:
- **2 GB RAM. Never build the frontend on it** — it OOMs. Builds go through GitHub Actions.
- **nginx blocks curl/wget user agents** (returns HTTP 444). Test from a browser, not curl. Do not
  waste time debugging 444s.
- `docker compose restart` does **not** reload env vars or clear nginx's DNS cache. Use
  `up -d --no-deps`, or a full `docker rm -f` + `up -d` for nginx.
- `pos-system_certbot_certs` holds certs for **three** projects. Never wildcard-delete inside it.

---

## Chick Shack UK domain — `chickshackg84.com`

**Status: ✅ LIVE on Cloudflare Workers as of 2026-07-27.** Worker version `d02f7fa5`.
Both apex and `www` serve the storefront over Cloudflare-issued SSL.

### How it got there

1. Domain is registered at **Fasthosts** (account `uk1517237781`, expiry 27-Mar-2027). The package is
   **"Email and Web Forwarding"** — no webspace, no FTP, no SSL. It could never host our stack.
2. Nameservers moved to **Cloudflare** (`daisy` / `vick.ns.cloudflare.com`) on 2026-07-27.
3. `wrangler deploy` initially failed with
   `Hostname 'chickshackg84.com' already has externally managed DNS records ... [code: 100117]`.
   Two dead Vercel records from a previous developer occupied the hostname.
4. Deleting **exactly** `A @ → 216.198.79.1` and `CNAME www → b00d3203a061e681.vercel-dns-017.com`
   cleared it. Deploy then attached both custom domains.

### ⚠️⚠️ This domain carries the client's LIVE EMAIL

**Never delete or proxy these records:**

| Record | Value |
|---|---|
| `MX` | `mailserver.livemail.co.uk` |
| `TXT` (SPF) | `v=spf1 mx a include:_spf.livemail.co.uk ~all` |
| `TXT` `_dmarc` | `v=DMARC1; p=none;` |
| `CNAME` `livemail1-4._domainkey` | `livemail{1..4}._domainkey.1404674.dkim.livemail.co.uk` |

All seven were **re-verified present and resolving after the 2026-07-27 change.**

**Cloudflare's auto-import silently dropped all four DKIM records** during the nameserver migration.
They were caught by diffing against the captured Fasthosts list before activation and re-added by
hand. **Never trust a DNS auto-import — diff it record by record** against
`_context/clients/chick-shack-uk/hosting-dns-reference.md`.

The two `_vercel` domain-verify TXT records were **deliberately left in place**. They sit on a
different hostname so they never conflicted with the Workers custom domain, and deleting them revokes
the previous developer's claim on the domain — a separate decision while ownership is unresolved.

### ⚠️ Verifying a DNS change: trust the authoritative nameserver, not your resolver

After the 2026-07-27 change, **the local router at `192.168.1.1` kept serving the dead
`216.198.79.1` for a long time**, so both a browser and `curl` on the LAN reported
`Server: Vercel / DEPLOYMENT_NOT_FOUND` well after the site was genuinely live.
`ipconfig /flushdns` did **not** help — it clears Windows' cache, and Windows then re-asks the router,
which answers from its own stale cache.

Verify with one of these instead:
```bash
nslookup -type=A <domain> daisy.ns.cloudflare.com     # authoritative, bypasses all caches
curl --resolve <domain>:443:<edge-ip> https://<domain>
curl -s -H 'accept: application/dns-json' 'https://1.1.1.1/dns-query?name=<domain>&type=A'
```
And confirm from a genuinely different network (phone on mobile data) before declaring it live to
anyone.

### Cloudflare access limits

The authenticated `wrangler` token (`Mallikamiin@gmail.com`, account
`cf6f829b0a562dcbeff59a286900c25f`) has **`zone (read)` only — no `dns_records:edit`** — and there is
no Cloudflare API token in `_context/secrets/`. **DNS record changes need a human at the dashboard**
or a scoped API token. Deploys, Workers and SSL are fine.

### ⚠️ Fasthosts scope discipline

The account also exposes `chickanas.com`, `chick-shack.com`, `chickshackg84.co.uk`,
`supra-security.co.uk`, `supra-security.com`. Access is visible but **not authorised**. Imran's
instruction: *"Only work on domain: Chickshackg84.com"*. Password rotated and 2FA enabled 2026-07-27.

---

## Deployment mechanics (POS)

- Compose: `docker-compose.demo.yml --env-file .env.demo`
- CI/CD: GitHub Actions builds the frontend on a 7 GB runner, deploys via SSH + `Dockerfile.prebuilt`
- **Always back up `.env.demo` before any server change.** Deleting it caused a 2-hour outage on
  2026-03-25.
- **Never `docker compose down -v`** in production — destroys data and certs.
- **Never `rsync --delete`** to production — it wiped the server on 2026-03-25.
- **Always `pg_dump` before any operation that modifies data.** No exceptions.
- Run `server-preflight.ps1` before SSH.

### Storefront deploy

```bash
cd storefront && npm run build && npx wrangler deploy
```
Static assets only, no worker script. Routes live in `wrangler.toml`. Cloudflare handles DNS and SSL
for the custom domains automatically.

---

## Known-bad / open

- **Nightly demo-data cron is non-functional** — see `open-items.md`. It has never once run.
- **`memory/server-deployment-rules.md` inventory is incomplete** — it does not mention
  `parkcity.sitaratech.info`/Orbit sharing this nginx.
- **3 server-local config files drift from git**: `docker/nginx/nginx.conf` (gzip block) and
  `frontend/.dockerignore` exist on the server but were never committed.
- **Stray Docker volumes** `pos-system_certbot-etc` and `pos-system_certbot-var` are redundant since
  the cert merge. Safe to remove, not urgent.
