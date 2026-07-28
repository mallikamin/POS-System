# HANDOFF — 2026-07-29 ~00:05 PKT

Read `STATE.md` first. This is the delta from the session that ended here, plus the next
steps Malik asked for. The previous handoff is archived at
`docs/history/HANDOFF_2026-07-27.md`.

---

## Where things stand

**Deployed to production and verified on the server:**

| | |
|---|---|
| Server HEAD | `4e14680` |
| Migration | `n0o1p2q3r4s5` applied — the deploy workflow now runs migrations, with a `pg_dump` first |
| Backend | healthy, database and redis green |
| nginx | recreated after the backend rebuild; **both** `default.conf` and `voice.conf` mounted |
| `chick-shack` tenant | seeded: 8 categories, **62 items**, 3 modifier groups, **11 delivery areas**, GBP, Europe/London |
| Other tenants | `cosa-nostra` (208 items), `demo-restaurant` (43 items) — untouched |
| Login sheet | `C:\Users\Malik\Downloads\ChickShack-PRODUCTION.txt` (server copies removed) |
| Backups | `~/pos-system/backups/pre_migrate_*.sql` and `pre_chickshack_seed_*.sql` |

**Not yet done: nobody has opened either site in a browser.** Rule 5 requires verifying
`eats.sitaratech.info` **and** `orbit-voice.duckdns.org` after any nginx work. Do that first.

Imran's tablet URL:

    https://eats.sitaratech.info/online-orders?shop=chick-shack

`?shop=` is remembered in localStorage, so it survives the login redirect.

---

## Two known issues, neither blocking

**1. The deploy's "Verify deployment" step always fails.** It uses `curl`, and this nginx
blocks curl with HTTP 444 by design (Rule 4). The deploy itself succeeds; only the check
lies — and it is what generates the failure emails. Fix by checking from inside:

    docker exec pos-system-backend-1 python -c "import urllib.request; \
      print(urllib.request.urlopen('http://localhost:8000/api/v1/health').read())"

**2. Every deploy leaves nginx pointing at the old backend IP.** The workflow recreates
backend and frontend but not nginx, so a 502 is expected after each run until nginx is
recreated by hand. Automating it is safe **only** with the mount check in front —
`docker-compose.demo.yml` currently declares all four required mounts, including
`/root/orbit-crm/voice.conf`. Do not add the step without re-verifying that list.

---

## What Malik asked for next

### A. Two UAT runs

1. **We place an order**, Imran accepts it on the tablet, and we watch it print. Proves the
   chain on his hardware.
2. **Imran places an order himself on the website**, then accepts it on the tablet.
   End to end, his hands only.

⚠️ **The storefront checkout is still not wired.** `place()` in
`storefront/src/components/Checkout.tsx` fabricates a reference and creates nothing, and
`SHOP.orderingEnabled` is `false`. **Run 2 is impossible until that is done** — OI-28 and
OI-37. Run 1 works today by posting to the public API directly.

The scratchpad script `e2e_order_flow.py` from this session does exactly that against
localhost and is the fastest starting point — repoint it at the production host and the
`chick-shack` slug.

### B. The real design gap Malik spotted

> *"how will an order be served/delivered? how will we tell the POS that?"*

He is right, and it is not built. Today an online order goes:

    placed -> accepted -> in_kitchen -> (nothing)

`accept_order` sets `status = "in_kitchen"` and creates a kitchen ticket. **There is no way
for the shop to say "this went out" or "the customer collected it."** The order sits in
`in_kitchen` forever, so the Active tab grows without bound and takings never settle.

Reuse what exists rather than inventing:

- The order state machine already has `ready → served → completed`.
- `PATCH /orders/{id}` already drives those transitions for till orders.
- Payment status is separate from order status, which matters here: cash on delivery is
  paid at the door, *after* it leaves.

Suggested minimum, matching what Imran described and nothing more:

| Service type | Button on the Active card | Transition |
|---|---|---|
| Collection | **Collected** | → `served` → `completed` |
| Delivery | **Out for delivery**, then **Delivered** | → `ready` → `served` → `completed` |

Cash orders need the payment recorded at the same moment or the Z-report will not balance.
Decide whether "Delivered" also marks a cash order paid, or whether that is a second tap.
**Ask Imran** — his answer decides whether the driver or the shop closes the order.

### C. Backend tests before proceeding

Malik asked for these explicitly. Current state: **342 passing**, 12 failing, and all 12 are
pre-existing and unrelated (10 parked QB Desktop, 2 stale order assertions — OI-34). Run
with the venv built this session:

    cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q

New this session: `test_public_tenant_routing.py` (17) and `test_pin_tenant_isolation.py` (8).

---

## Things worth not forgetting

- **`.env.demo` and `droplet.txt` are tracked in git.** `.env.demo` carries production
  QuickBooks credentials, the database password and `SECRET_KEY`. It is also modified on the
  server, so `git pull` there only works while no commit touches it — and the workflow
  swallows a failed pull with `|| true`. Worth addressing deliberately.
  `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` sits untracked in the repo root where a
  `git add .` would sweep it in. Never `git add .` in this repo.
- **OI-39:** on the *local* database, Chick Shack's 11 delivery areas were seeded onto
  `demo-restaurant` on 07-27 and are still there. Production was never affected. Removing
  them is a judgement call, not a cleanup.
- **OI-38:** the seed sets tax to **0**, deliberately, rather than assuming 20% UK VAT.
  Ask Imran whether Chick Shack is VAT registered before real money moves.
- The printer's software path is proven byte for byte (4 × `0x9C`, 48 columns, partial cut).
  The only untested link is whether Chrome on his Android honours the `rawbt:` scheme or
  needs the `intent:` fallback — 30 seconds on his tablet.
