# STATE — Restaurant POS System

**Last refreshed:** 2026-07-29 (session D) · **Branch:** `main` · **HEAD:** `513e6e8`, pushed **and deployed**

🔴 **THE STOREFRONT IS PUBLISHED AND `chickshackg84.com` IS TAKING REAL ORDERS, 24/7.**
Published 2026-07-29 ~00:30 UK. **There is no time gate** — an order placed while the shop is shut
is accepted as a **pre-order** and labelled as one on the website, the confirmation page and the
tablet. Refusing out-of-hours customers was tried and reversed: it loses the order to whoever is
still taking them. Nothing is auto-accepted; Imran's team still accepts or rejects every order by
hand. **Any real order now goes straight to his tablet — UAT is live.**

*2026-07-29 (late session): merged to `main` and deployed. The **whole order lifecycle** is now
wired end to end — tablet buttons for out-for-delivery / delivered / mark-paid, completed orders
leave the Active tab, and the customer's confirmation page follows it. Storefront gained required
email, **"leave it out" ticks** that print in bold on the kitchen ticket, and an ordering window.
Migration `o1p2q3r4s5t6` (`orders.customer_email`) **applied on production** — verified in the
backend's own upgrade log, not assumed. Backend suite **373 passing** (was 342), same 12
pre-existing failures — **re-run and verified at 373 on 2026-07-29 session D**, not inherited
from a checkpoint claim.*

*⚠️ **Two silent deployment bugs were found and fixed** — both had been live for an unknown
number of deploys. The deploy script was being truncated by its own `pg_dump` reading stdin, so
`alembic upgrade head` had **never run** from CI; and `git pull || true` was hiding a refused
pull, so the **backend had been stale on the server at `b0dbb6a`** while the frontend kept
updating. Full write-ups in `ERROR_LOG.md`. The deploy now recreates nginx itself and verifies
every hostname's certificate, so "merge to main" is a complete deploy with no hand-fixing.*

*Email still sends **nothing**: no SMTP provider and no sending domain chosen. See OI-43.*
*2026-07-29: everything below was **committed, pushed and deployed to production**. Migration
`n0o1p2q3r4s5` applied on the server, `chick-shack` seeded there (62 items), `eats.sitaratech.info`
finally given its own certificate. Backend suite 342 passing, same 12 pre-existing failures.
Prior sessions: `PAUSE_CHECKPOINT_2026-07-29.md`, `_state/sessions/2026-07-27_0700.md`.*
*2026-07-28: the printer prints, walked through remotely with Imran. Multi-tenant routing fixed
(a real cross-tenant PIN flaw), Chick Shack tenant + 62-item menu seeded, logins verified.*

> ⚠️ The 99 dirty paths in the working tree are **not** current work. They are a pre-existing bulk
> edit that added a QA notice to ~50 markdown docs, plus 13 unstaged `PAUSE_CHECKPOINT_*` moves into
> `docs/history/`. Left alone deliberately. **Never `git add .` in this repo** (`.env.demo` is tracked
> and carries live credentials).

**This file is the dashboard and the authoritative entry point. Read it first, then one topic file.**
Detail lives in `_state/`. History lives in `docs/history/` and is never current.
New here? → **`_state/README.md`**.

---

## Current focus

**Chick Shack UK — online ordering channel.** A UK takeaway keeps its EposNow till for in-house trade;
we supply the online channel alongside it: website with checkout, plus a tablet showing live orders.
£300 build + £35/month, paid at go-live. **Not a POS displacement.**

🔴 **The storefront is live at https://chickshackg84.com and TAKING ORDERS 24/7** — out-of-hours
orders are accepted as labelled pre-orders, never refused.

---

## Live status

| Area | Status | Detail |
|---|---|---|
| Chick Shack storefront | ✅ **Live** on the client's real domain, Cloudflare SSL | `_state/chick-shack-uk.md` |
| Chick Shack ordering | 🔴 **LIVE, 24/7.** Out-of-hours orders are accepted as **pre-orders** and shown as such on all three surfaces. Accept/reject is always manual | `_state/chick-shack-uk.md` |
| Chick Shack tenant + menu in DB | ✅ **Seeded locally and on production 2026-07-28/29** — 8 categories, 62 items, 11 delivery areas, GBP. Logins verified | `_state/decisions.md` D-11 |
| Multi-tenant routing | ✅ **Fixed 2026-07-28.** Public routes keyed by slug; PIN login no longer searches across tenants | `_state/decisions.md` D-10 |
| Public ordering API | ✅ Built, tenant-scoped, queue endpoint. **Deployed 2026-07-29** | `_state/chick-shack-uk.md` |
| Order-queue tablet view | ✅ **Deployed with the full lifecycle** at `/online-orders`. Accept → out for delivery → delivered/paid; completed orders leave Active. **Not yet opened on Imran's real tablet** | `_state/open-items.md` OI-36 |
| Storefront checkout wiring | ✅ **Merged and PUBLISHED 2026-07-29.** Menu from the API, checkout posts, confirmation follows the order to delivered. Email required; "leave it out" ticks print on the ticket | `_state/open-items.md` OI-28 / OI-37 |
| API access from the storefront domain | ✅ **Fixed on the server 2026-07-29.** `CORS_ORIGINS` now allows both Chick Shack origins; preflight verified, unknown origins still refused | `_state/open-items.md` OI-40 |
| Stripe | ⬜ Not started. Blocked on the client's account. Not needed for either UAT run | `_state/open-items.md` OI-20 |
| Printing | ✅ **PROVEN ON SITE 2026-07-28.** The tablet printed to his existing EposNow printer. £0 hardware. Our own bytes still not on paper | `_state/printing.md` |
| Served / delivered gap | ✅ **CLOSED and deployed.** Tablet has out-for-delivery / delivered / mark-paid; completed orders leave the Active tab; the customer's page follows it | `_state/open-items.md` OI-44 |
| Customer emails | 🔶 **Code done, sends nothing.** 4 messages built and wired; gated on `settings.email_configured` = `SMTP_HOST and EMAIL_FROM`, and **no email key exists in any env file.** `Reply-To` **is** now set (`e0168c4`). Provider **chosen: Mailjet free**, address `orders@chickshackg84.com`. Only the account + one DNS record + server env remain — `docs/EMAIL_SETUP_RUNBOOK.md` | `_state/open-items.md` OI-43 |
| Menu modifier prompts | ⏸️ **Parked to QC by Malik 03:09.** Imran wants a required Hot/Mild "Peri-Peri Heat" choice on peri items (easy, no schema change) **and** meal-contents choices (hard, conditional). Requirement still incomplete — he was mid-list | `_state/open-items.md` OI-45 |
| Backend test suite | ✅ **371 passing** (2026-07-29 late), same 12 pre-existing failures. **29 new** cover the lifecycle guards + email; the shipped lifecycle/email code had had zero tests | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| CI (`ci.yml`) | ❌ **Red on every commit.** Ruff + ESLint fail; Ruff exits before the test step, so **CI has never run the suite**. All findings are in parked code, none are live bugs. Deploys are a separate workflow and are green | `_state/open-items.md` OI-47 |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |

---

## Next action

**Everything is deployed and published.** `merge to main` is now a complete deploy: it recreates
nginx itself and verifies every hostname's certificate, so there is no hand-fixing step any more.

🔴 **UAT is live NOW.** `chickshackg84.com` accepts orders at any hour and every one lands on
Imran's tablet at `https://eats.sitaratech.info/online-orders?shop=chick-shack`. **Tell Imran.**

In order:

1. **Tell Imran the site is live** and that orders start arriving from 14:00. He has never opened
   the tablet page on the real device (OI-36) — that is the single biggest untested link.
2. **UAT run 1**: we place an order, Imran accepts on the tablet, the ticket prints.
3. **UAT run 2**: Imran places the order himself, then drives it accept → out for delivery →
   delivered, and confirms the takings settle.
4. **Email — the next task.** Nothing sends. Provider **chosen: Mailjet free**, address
   `orders@chickshackg84.com` on the **apex** (the earlier `mail.` subdomain suggestion is
   **withdrawn** — unnecessary once we skip Mailjet's SPF instruction, and a subdomain sender
   is a weaker DMARC story than an aligned apex DKIM). **One additive TXT record; nothing
   existing is modified**, because DMARC passes on DKIM alignment alone and the single live SPF
   record must not be edited on a domain carrying the client's business email. `Reply-To` is
   already in the code (`e0168c4`). **Follow `docs/EMAIL_SETUP_RUNBOOK.md` exactly.** See OI-43.
5. **OI-45 menu modifiers**, now fully specified by his screen recording. No schema change needed.
6. **Stripe** (OI-20) — still blocked on his account. Until then every order is created unpaid and
   `cardPaymentEnabled` stays `false`.

**Waiting on the client (not blocking the build):**
- The **Stripe account** needs connecting (OI-20). Ask before starting step 5.
- **Is Chick Shack VAT registered?** (OI-38). Tax is seeded at 0 deliberately. Must be answered
  before real money moves.

---

## Read before you touch anything

| If you are… | Read |
|---|---|
| Working on the client build | `_state/chick-shack-uk.md` |
| Touching a server, domain or DNS | `_state/infrastructure.md` **and** `memory/server-deployment-rules.md` |
| Touching the database | `memory/data-integrity.md` — **`pg_dump` first, no exceptions** |
| Debugging something odd | `ERROR_LOG.md` — it is a real log of real mistakes |
| About to re-argue a decision | `_state/decisions.md` — it may already be settled and logged |
| Picking up work | `_state/open-items.md` |

**Standing cautions.** The DigitalOcean box is **shared** with two other projects behind one nginx —
`docker ps -a` and check volume mounts before any container operation. `chickshackg84.com` carries
the client's **live email**; only ever touch its `A` and `www` records. Never echo a credential.
