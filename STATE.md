# STATE — Restaurant POS System

**Last refreshed:** 2026-08-26 (late evening, THIRD fresh session via HANDOFF.md; `/refresh` run).
**One drift corrected. No contradiction on substance.** Git re-verified against the real remote,
not the tracking ref: HEAD **`c23b574`**, `git ls-remote origin main` = **`be7abc8`**,
**1 UNPUSHED COMMIT**, 144 dirty files. **No code, storefront or server change on this refresh pass.**

⚠️ **Drift corrected on this pass:** the header above previously read HEAD `be7abc8` / **0 unpushed**,
and this file recorded the procurement work only as "built, local only" without naming a commit.
It was committed as **`c23b574`** (42 files, +13,555 lines) at the end of the previous session and
is **unpushed**. The substance was already right (built, verified locally, not deployed); only the
commit identity and the unpushed count were stale. `c23b574` audited this pass: **it contains no
proposal file and no credential-bearing script** - the `proposal/`, `seed_fz_llc`, `system_admin`
and `verify_*` files are all still correctly untracked, and all six are present on disk.

🔴 **DEPLOY IS BLOCKED ON A TIMING DECISION, NOT ON THE CODE.** At this refresh it is **19:36 UK
on Wednesday 2026-08-26**. Chick Shack trades **16:00-22:00 UK, 7 days**
(`_context/clients/chick-shack-uk/menu.md`), so the shop is **OPEN and mid-service**, closing at
**22:00 UK = 02:00 PKT**. `git push origin main` IS the deploy and it recreates the SHARED nginx
serving Chick Shack's live tablet.

🟢 **DEPLOYED AND VERIFIED, 2026-08-26 ~20:55 UK. `a874fb9` IS LIVE ON PRODUCTION.**
Malik cleared it: *"ok we are wrapping up the chick shack. so its safe to initiate deployments and
all due tasks. over to u."* Deployed at **20:40-20:55 UK, inside service hours** (shop trades
16:00-22:00) on that explicit authorisation, as on 2026-08-22. Run `33011847686`, **success, 4m22s**,
every step green including migrations and the certificate check.

**Two commits shipped:** `c23b574` (procurement, PO workflow, OCR receiving, ordering engine,
quotations) and `a874fb9` (AI spend guardrails). 45 files. Server HEAD confirmed `a874fb9`.

🟢 **CHICK SHACK IS BYTE-IDENTICAL THROUGH THE DEPLOY. Measured before AND after, by the same
query, not assumed.**
| | before | after |
|---|---|---|
| orders | 233 | **233** |
| newest order | `2026-08-26 19:40:58.231546+00` | **identical** |
| customers | 166 | **166** |
| payments | 219 | **219** |
| payments total | 642087 | **642087** |
| menu items | 87 | **87** |
| users | 3 | **3** |

⚠️ **A scare worth recording so nobody re-panics.** The first baseline appeared to show customers
DOWN 172 to 166 and payments DOWN 222 to 219 against the previous session's recorded figures.
Investigated before deploying rather than after. **Nothing was deleted:** the old numbers were
measured **unscoped across all tenants** while these are scoped to chick-shack. All-tenant customers
175 (was 172, **+3**) and payments 227 (was 222, **+5**); `customers` has no soft-delete column and
all 219 chick-shack payments are `completed`. **Measure the same way both times or the comparison is
meaningless.**

**Also verified, not assumed:** all FOUR hostnames return 200 **each serving its own certificate**,
`parkcity.sitaratech.info` included (the workflow does not check that one); `/api/v1/health` 200;
Orbit CRM up and untouched; `alembic_version` = `a3b4c5d6e7f8`; all seven new tables present
(`suppliers, purchase_orders, purchase_order_items, goods_receipts, quotations, ai_usage_log,
locations`); and the new guardrails confirmed live **inside the running container**, not merely
committed.

🟢 **AI is OFF on production and that is the correct state.** Read from the running backend:
`ai_configured = False`, cost cap `5.00`, tenants allowed to spend = **none**. Both locks are shut.
Nothing can spend until a key AND `AI_ENABLED_TENANT_SLUGS=martin-fz` are set in `.env.demo`.

🟢 **The storefront was NOT touched.** No file under `storefront/` is in this push, so the separate
Cloudflare pipeline needed no deploy and Chick Shack's customer site is unchanged.
`chickshackg84.com` verified 200 after the deploy. This is the two-pipeline rule holding, checked
rather than trusted.

**Pre-deploy backup:** `/root/backups/pos_pre_procurement_20260826T204142Z.sql.gz`, 375K, 47 table
data blocks, verified non-empty before the push. The deploy took its own `pre_migrate_*` dump as well.

📌 **`.env.example` was updated locally with the new variables but deliberately NOT committed** - the
`cred-guard` hook blocks git operations naming that path, and the hook was not worked around. The
same documentation exists in `config.py` and in both compose files, so nothing is lost.

📌 **`OI-93` opened on this pass, DEFERRED until after Martin. There is no per-tenant module
entitlement in this system.** Malik believed Chick Shack would need the supplier module "given
access" before they could use it. **They would not.** Verified three ways: no entitlement field
exists on `tenants` or `restaurant_configs`; `require_role` checks only the role NAME
(`deps.py:93`); the admin sidebar is a static array with no tenant conditional
(`AdminLayout.tsx:53-54`). Chick Shack has 2 active admin users, so their admin sees Suppliers and
Purchase Orders today. **Tenant data isolation is NOT affected and remains proven** - the exposure
is commercial (they bought the online channel and can see the whole back office), not a leak.
⚠️ Not the same thing as the AI `AI_ENABLED_TENANT_SLUGS` allowlist, which only stops other tenants
SPENDING, not SEEING. Full detail in `_state/open-items.md`.

📌 **`OI-92` opened on this pass and DEFERRED by Malik until Martin's work is complete.** Deployment
hygiene: the deploy needs a closed-shop window today, and that does not survive a fifth tenant. The
measured facts and the full ranked fix are in `_state/open-items.md`. In one line: the deploy has a
stop-the-world step because **nginx caches upstream container IPs at config load**, which is the only
reason a POS deploy can reach Chick Shack and Orbit CRM at all; a `resolver 127.0.0.11` plus a
variable `proxy_pass` removes it in about 10 lines, and serving the frontend from a bind-mounted
symlink removes the other one. **Measured, not estimated: the whole server-side deploy script runs in
72 seconds** (run `32964635563`), and the window a tenant can actually 502 in is under a minute of
that. An earlier in-session estimate of "about 5 minutes" was a guess and was wrong.

**Last refreshed (previous):** 2026-08-26 (evening, second fresh session via HANDOFF.md; `/refresh` run).
**Verified current, four small drifts corrected, no contradiction on substance.**
Git re-verified this pass, against the real remote not the tracking ref: HEAD `be7abc8`,
`git ls-remote origin main` = `be7abc8`, **0 unpushed**, 138 dirty files. **No code, storefront or
server change on this refresh pass.**

⚠️ **Drifts corrected on that pass:**
1. **`HANDOFF.md` and `PAUSE_CHECKPOINT_2026-08-26-B.md` both name HEAD as `815a21e`. It is
   `be7abc8`.** The docs commit `be7abc8` was made and pushed at 17:07 PKT, after the checkpoint
   was written. `0 unpushed` still holds, so the substance is unchanged, but both files are one
   commit stale.
2. 🟢 **That push fired a production deploy neither file records** (`Deploy to Production` run
   `32966929610`, **success**, 3m24s, 12:08 UTC). Docs-only diff, so no behaviour change was
   expected. **Verified independently rather than assumed: all FOUR production hostnames return
   200** with a browser UA, `parkcity.sitaratech.info` included (the workflow does not check that
   one). Chick Shack row counts NOT re-measured this pass; the documented baseline stands and will
   be re-measured immediately before the next deploy, which is the point at which it is load-bearing.
3. **The STATE.md header itself was stale** (it read `cd57170` / origin `50a8002` / 1 unpushed /
   149 dirty, from the morning pass) even though this same file's own sections below already
   recorded the two deploys that followed. Header corrected above.
4. ⚠️ **`_context/clients/fz-llc-uae/plan-and-todo_2026-08-26.md` contradicts itself.** Its newest
   top section is current, but the older lower half still says the 2-location model is "not
   started", the A4 tax invoice is "not started", the universal system-admin login is "NOT applied
   to production", and everything is "local dev only". **All four are now false.** The top section
   supersedes. Flagged rather than silently merged because a reader landing mid-file is misled.

📌 Known and unchanged, not new failures: the `CI` workflow is red (47s) and `Deploy to Staging`
fails in 12s. That is **OI-80**, long-standing, no signal. `Deploy to Production` is the pipeline
that matters and it is green on both `815a21e` and `be7abc8`. Local dev stack is up: all five
`pos-system-*` containers healthy.

**Last refreshed (previous):** 2026-08-26 (fresh session via HANDOFF.md; `/refresh` run). ⚠️ **STATE.md was a
whole session stale on entry** — it carried **no record at all** of the 2026-08-26 FZ LLC (Martin
Zubeldia, UAE) build session: sub-recipe production chain, the Postgres tz bug fix, the `martin-fz`
tenant, and the universal system-admin login were all missing. Reconstructed below from
`PAUSE_CHECKPOINT_2026-08-26.md` and `_context/clients/fz-llc-uae/plan-and-todo_2026-08-26.md`.
Git re-verified: HEAD `cd57170`, `git ls-remote origin main` = `50a8002`, **1 unpushed docs commit**,
**149 dirty files** (STATE said 138; the delta is this session's untracked FZ LLC files, not drift).
**No code, storefront or server change on this refresh pass.** 🔴 **The live priority is now FZ LLC,
not Chick Shack** — Martin's written quote + a client-visible demo URL are due **Monday 2026-08-31**.

**Last refreshed (previous):** 2026-08-25 (second pass, same day, FB Live feasibility for the Chick Shack Page,
**OI-91 opened**). Git re-verified: HEAD `cd57170`, `git ls-remote origin main` = `50a8002`, **1
unpushed docs commit**, 138 dirty files (STATE said 130, routine scratch drift, not a code change).
**No code, storefront or server change this pass.** New material fact: **Meta's own Help Centre
gates live-streaming-from-software at 60-day account age AND 100 Page followers**, Chick Shack has
**58 followers**, so the FB Live idea is **blocked on a number, not on our architecture**. See the
🔴 FB LIVE section below. The "page had to be 2 months old" report (via Bilal Waheed / ccbw) is
**confirmed real** and is the 60-day half of that same rule.

**Last refreshed (previous):** 2026-08-25 (OI-72 Meta Page-access handover, RESUMED). Git unchanged since
08-22 except one unpushed docs commit `cd57170`; HEAD `cd57170`, `origin/main` = `50a8002`, server at
`50a8002`, 130 dirty files. **No code or storefront change this pass.** ⚠️ `cd57170` is still
unpushed and pushing it re-runs the deploy pipeline, so it must wait for a closed-shop window.
Material new fact this pass: **Imran has NO business portfolio** (verified from three of his own
screenshots, see the 08-25 section below), which answers unverified item (3) from the 08-08
diagnosis and kills the portfolio route. ⚠️ An earlier claim on this same refresh that a
portfolio DID exist was **wrong** and is corrected in place below.

**Last refreshed (previous):** 2026-08-22 ~20:45 UK. **OI-89 + OI-90 SHIPPED AND VERIFIED LIVE (`50a8002`),
deployed DURING service on Malik's instruction, tested by Imran on the shop printer.** Git: HEAD
`50a8002` = `origin/main`, server at `50a8002`, tag `pre-oi89` (= `4b11c43`) pushed. One docs commit
may sit unpushed after this refresh (see the 08-22 section); pushing it re-runs the deploy pipeline,
so it waits for the 22:00 UK close. Section for OI-89/90 below updated from "mockups" to "live".

**Last refreshed (previous):** 2026-08-20 (Chick Shack refresh + Meta Page-access handover, PAUSED mid-flow).
Git re-verified this pass: HEAD `4b11c43`, `git ls-remote origin main` = `4b11c43`, **0 unpushed**,
132 dirty files (was 128). **No code or storefront change since the 08-17 deploy.** No dated file
newer than this one exists, so nothing contradicted STATE this pass. New section added below for
OI-72 (Page access).
Content below unchanged from the 2026-08-18 ~21:55 UK refresh. **HEAD `4b11c43`**, branch
`main`. ✅ **origin/main is now `4b11c43` and the server is at `4b11c43` — 0 unpushed. The
08-17 scheduled deploy fired.**
Container start times read from `docker inspect`: nginx/frontend/backend all
**2026-08-17T21:32-21:33 UTC = 22:32 UK**, exactly the armed time. Storefront at Cloudflare
`c8d8a9b6`, unchanged (no storefront work since). **128 dirty files.**

⚠️ **Three drifts corrected on this refresh, all of them recorded here rather than silently merged.**
1. **STATE.md was a whole session stale.** Its header said `1bcdb7b`, 0 unpushed, and the file
   carried **no OI-85, OI-86 or OI-87 section at all**: the entire 2026-08-17 session (campaign
   judged, OI-86 built, deploy script generalised, OI-87 opened) was missing. Added below.
2. 🔴 **"3 commits ahead" is wrong; it is 5.** `HANDOFF.md` and `PAUSE_CHECKPOINT_2026-08-17-B.md`
   both name three unpushed commits (`565b42e`, `ad5e8ef`, `4b11c43`) and miss the two docs commits
   underneath them, **`b5dcf21`** and **`2fc48f4`**. Verified against the real remote with
   `git ls-remote` (`origin/main = 19ee3d1`), not the local tracking ref. Consequence, and it is
   benign but should not be a surprise: tonight's deploy pushes **all five**, so the two OI-86
   framing docs ship with it.
3. **`_state/open-items.md` still headed OI-86 "NOT BUILT … storefront-only, ships via Cloudflare".**
   It was built, backend-side, and committed as `565b42e` (5 files, +391 lines, incl.
   `email_normalise.py` and 2 test files). Register header corrected on this refresh; the decision
   record beneath it was already right.

**Open:** 🔴 **FZ LLC / Martin Zubeldia (UAE) — the live priority, hard deadline Monday 2026-08-31**:
two-tier written quote + a client-visible demo URL, plus the unbuilt scope list (2-location model,
per-channel net-profit, A4 tax invoice, supplier/PO, OCR receiving, AI PO suggestions, sub-recipe
admin UI). See the 2026-08-26 section immediately below. Then the Chick Shack items: **OI-91** (FB Live on the Chick Shack Page, **blocked by Meta's 100-follower / 60-day
eligibility gate, Page has 58**; opened on the 08-25 second pass, see below), **OI-72** (Meta Page access handover, **resumed 08-25, portfolio confirmed, mid-flow on Imran's laptop**, see below), **OI-88** (delivery minimum is flat £5 while the fee bands run £3 to £15, opened on this
refresh, see below), **OI-87** (push our online orders into EposNow, researched), **OI-86**
(built, committed and now **deployed**; effect in production still unverified), **OI-85** (Google review email converts at zero,
undiagnosed), **OI-83** (campaign sent, **zero second orders**; decide whether to run another),
**OI-82** (discount analysis, nothing sent to Imran), **OI-80** (CI red, no signal), **OI-76**
(what3words reply drafted, unsent), one-click unsubscribe, HSTS, and Malik's tip-flow and chips-flow
UATs.

## 🟢 2026-08-27 (~23:10 UK). UAT RUN ON PRODUCTION, 9 FINDINGS, ALL FIXED AND DEPLOYED (`f3c6759`). CHICK SHACK BYTE-IDENTICAL THROUGH BOTH DEPLOYS.

**Malik drove UAT himself on production, one step at a time, exercises 1-4 of the playbook.**
He stopped at 02:40 PKT on the recommendation to let the batch be built rather than continue.
**Exercises 5-15 are still to run** on the fixed system.

🔴 **THE FINDING THAT MATTERED: the stock movement ledger was written but unreadable.**
`stock_service.move_stock` has written an `InventoryTransaction` for every stock change since the
module shipped, and the adjust endpoint has always demanded a mandatory reason. **There was no
endpoint and no screen that read any of it** (grepped the whole API and schema layer: nothing).
So the reason a human typed went into the database and could never be seen again. Two consequences:
the client walkthrough PDF told Martin to *"look at the movement history for that item"* and there
was no such thing, and **"stock never changes without an explanation" was a claim the customer had
to take on trust.** Now built: a read path over the ledger and a History panel per stock row
showing what changed, the running balance, who did it and why. The joins are LEFT deliberately, and
there is a test for it: a movement with no performer was done by the system, and an inner join
would have hidden every sale while looking complete.

**All nine findings, all fixed in `f3c6759`:**
| # | Finding | Nature |
|---|---|---|
| 1 | Stock movement ledger written but unreadable | 🔴 feature gap, deliverable pointed at a screen that did not exist |
| 2 | Any URL could overwrite a device's remembered restaurant, unauthenticated | 🔴 real risk: a tablet that opened a foreign `?shop=` would aim the next PIN login at the wrong tenant (the OI-69 failure) |
| 3 | `/login?shop=X` ignored by an existing session | demo link landed the reader in another shop |
| 4 | `RestaurantConfig.name` declared but API returns `restaurant_name` | always `undefined`; caused "Restaurant not loaded" |
| 5 | Session could not say which tenant it owned | frontend inferred it from the value bug 2 could corrupt; `tenant_slug` now in the config response |
| 6 | Admin sidebar had no scrollbar | 22 modules, last entries unreachable without zooming out |
| 7 | Dine-In + Table Utilization shown to a business with no tables | plus two QuickBooks entries for an integration never bought |
| 8 | Header said "POS System" for every tenant | next to a comment reading "Restaurant name" |
| 9 | Seeded reorder points were `quantity/6` to 3 decimals | "reorder point 4.167 L" reads as unfinished |

**New: `restaurant_configs.hidden_ui_modules`**, a per-tenant slug list hiding nav entries, channel
tiles and dashboard cards. ⚠️ **PRESENTATION ONLY, and there is a test pinning that** so nobody
later reads it as access control: it does not gate the endpoints, because every admin route is
gated by ROLE and nothing else. **The real per-tenant module gate is OI-93 and is not built.**
Set on production for **`martin-fz` only** (`dine-in,quickbooks-online,quickbooks-desktop`);
verified that chick-shack, cosa-nostra and demo-restaurant all read `(none hidden)`.

**Tests: 14 new** (8 ledger, 6 config). Full suite **765 passed**, same 12 failed + 2 errors as
clean HEAD. Migration `b4c5d6e7f8a9` additive with a server default,
upgrade/downgrade/upgrade round-tripped against Postgres.

🟢 **CHICK SHACK UNCHANGED THROUGH BOTH DEPLOYS OF THE NIGHT.** Measured before and after each,
by the same query: **233 orders, newest `2026-08-26 19:40:58`, 166 customers, 219 payments, 642087
total, 87 menu items** - identical at every measurement. No schema change to their data, no
order-flow change, no module hidden for them. `storefront/` was not touched by either commit, so
the Cloudflare pipeline needed no deploy; `chickshackg84.com` verified 200 afterwards regardless.
⚠️ **One visible change for them, flagged rather than buried:** their online reports header now
shows "Chick Shack" instead of the generic "Online Orders", a consequence of fixing finding 4.
Revertible on request.

**Verified beyond the green Action:** server HEAD `f3c6759`; `alembic_version` = `b4c5d6e7f8a9`;
all FOUR hostnames 200 each serving its own certificate (`parkcity` included, which the workflow
does not check); the new `/locations/stock/movements` route answers **401 not 404**; and the new
code was **grepped out of the DEPLOYED bundle on the box** (`StockPage-CZzLqCMg.js` contains
"Movement History", `locationsApi` contains `stock/movements`, `modules-Crco9ozz.js` exists) rather
than trusted from a green build.

**Backups before each deploy:** `/root/backups/pos_pre_procurement_20260826T204142Z.sql.gz` (375K,
47 table blocks) and `/root/backups/pos_pre_uatfixes_20260826T225944Z.sql.gz` (378K, 56 blocks).

**Still open for Martin:** exercises 5-15 of the UAT, the demo video, re-checking the walkthrough
PDF against the fixed system (exercise 4 now describes a screen that exists), and pricing last.
🔴 **Still blocked on Malik: which Anthropic key** Martin's demo uses, and whether the placeholder
TRN `100123456700003` on the A4 tax invoice is replaced or declared as dummy data.

## 🟢 2026-08-27 (late). AI SPEND GUARDRAILS BUILT FOR MARTIN. A $5/DAY MONEY CAP, AND THE BLOCKER THAT WOULD HAVE MADE THE KEY DO NOTHING.

**Malik's instruction:** *"yes we set it up for Martin with proper guardrails and rate limiting. we
dont want martin to be scanning 500 documents. just put a daily limit of lets say $5 for now (should
cover 3-5 docs at least) -- make sure proper playbook caching optimizations are in place. need no
surprises with a $1000 bill on API."* `api-cost-playbook` invoked, as the global rule requires.

**Not deployed. Local only, uncommitted.** Rides the same window as `c23b574`.

🔴 **THE BLOCKER, and it would have cost an hour at 02:00.** `docker-compose.demo.yml` is the
PRODUCTION compose file and it had **no AI environment passthrough at all**. The backend service
there has no `env_file:`, and `--env-file` only feeds `${...}` interpolation, so a key placed in
`.env.demo` would **never have reached the container**. The symptom is not an error: the deploy runs
green, the key looks right on disk, and the feature politely reports "AI is not configured on this
server". The file already documents this exact trap twice, for email and for Stripe. **Fixed: all
five AI vars now declared there.**

🔴 **There was no money cap, and the caps that existed were not what Malik thinks they were.**
The shipped caps were 200 calls and 2,000,000 tokens per tenant per day. Worked out against real
`claude-opus-5` pricing, those two together still permit about **$27.50 a day, roughly $825 a
month**: 200 calls x 4,000 max output = 800k output @ $25/Mtok = $20.00, plus the remaining 1.2M of
the token cap as input @ $6.25/Mtok = $7.50. **His "$1000 bill" fear was quantitatively justified
under the settings that were already in place.** A cap denominated in tokens is a cap in a unit
nobody budgets in.

**Built: `AI_DAILY_COST_CAP_USD_PER_TENANT`, default `5.00`.** Per tenant, per UTC day, checked
before the call, degrading gracefully like the others. All three caps kept deliberately: the money
cap binds and is the one to tune, but it derives from a rate table kept by hand and drifts if
Anthropic changes prices; the call and token caps are reported by the API and cannot drift.

🔴 **SECOND GAP, FOUND BY MALIK'S QUESTION, NOT BY ME: the feature was not Martin-only.** He asked
*"the API calls live only for martin. no other tenant is getting API calls feature?"* **The answer
was no.** The key is a server-wide setting and the two AI endpoints are gated by
`require_role("admin", "manager")` and nothing else. **No per-tenant AI flag existed anywhere** in
the codebase (grepped, not assumed). So a key on production would have switched the feature on for
**all four production tenants at once**, each with its own separate $5/day cap. **The true ceiling
was $20/day, about $600/month, not the $150 first reported to him.** Corrected out loud.

**Built: `AI_ENABLED_TENANT_SLUGS`, a comma-separated tenant allowlist**, enforced in
`_check_tenant_enabled` at the same single chokepoint, **before** the caps (a tenant that may not
spend at all should never have its daily total computed). **Empty means NO tenant, deliberately** -
a second opt-in lock alongside the key, failing in the safe direction. A forgotten setting surfaces
instantly as "AI is not enabled for this restaurant" and costs nothing; the opposite default would
fail silently by spending money. With `AI_ENABLED_TENANT_SLUGS=martin-fz` the ceiling is back to
**$5/day total**, and Chick Shack, parkcity and demo-restaurant cannot spend a cent.

⚠️ **Correcting Malik's number, because he sized the cap from it.** He expects $5/day to cover
"3-5 docs". **The measured cost is $0.026 per delivery-note scan**, so **$5/day is roughly 190
scans**, not 3-5. Off by about 40x. $5 is still a safe ceiling ($150/month worst case, versus $825
before), but if the intent was "a handful of documents", the number he actually wants is nearer
**$0.50/day (~19 scans)**. **His call, not made yet.**

⚠️ **It is a ceiling, not a budget.** Checked before the call, so a tenant at $4.99 is allowed one
more request. Worst overshoot is one call, a few cents.

**Caching, checked rather than assumed.** The B1 rule is genuinely implemented, not just claimed:
the static instruction block is cached, and the user message carries only the image plus a compact
numbered allowlist the model answers with INDEXES into, so the ingredient master is never sent.
📌 **Honest caveat worth keeping:** `cache_control: ephemeral` has a ~5 minute TTL. The measured
"1,563 written once, 3,126 read back" came from three calls in quick succession during verification.
In Martin's real pattern, a few scans hours apart, **almost every call will be a cache write at
1.25x, not a read at 0.1x.** The difference is about $0.002 a call, so it is not worth changing, but
the caching should not be sold as a saving in this workload.

**Tests: 17 new, in `backend/tests/test_ai_caps.py`. The caps had ZERO coverage before this.**
They were the only thing between a client tenant and a runaway invoice and nothing checked they
fired. Covers all three caps, the per-tenant isolation (Chick Shack cannot be locked out by the FZ
demo burning its allowance), UTC day rollover, failed-calls-still-count, an unknown model falling
back to the dearest rate rather than zero, and an F2 tripwire pinning Anthropic call sites to exactly
one file so a second uncapped one fails the build.

🔴 **A mistake of mine, recorded rather than buried: three of those tests made REAL, BILLED API
calls** on the first run, against Thrive Timesheet's key, which is still in the local container's
environment. They asserted "AI is not configured" as proof a cap had not fired, and the container
**is** configured. Cost is a fraction of a cent, but the principle is not: a test suite must never be
able to spend money. Fixed with an `autouse` fixture blanking the key for every test in the file.
Written up in `ERROR_LOG.md`.

**Full suite: 751 passed, 12 failed, 2 errors. Zero regressions.** The baseline is 736 passed with
10 failures; 736 + 17 new = 753, minus 2 = 751. The two extra failures are
`test_public_tenant_routing.py`'s date-range tests, **named explicitly in OI-63** as pre-existing
date-boundary failures, and the UTC/local date boundary rolled over mid-session. Verified against the
register, not assumed.

**`api-cost-playbook` outbound loop completed, as the global rule requires.** Logged in
`PLAYBOOK.md` Section L. Back-applicability to Thrive **verified by grep, not assumed**: Thrive has
no USD cap and no cost column at all, so it applies, and an OPEN item is filed in Thrive's `STATE.md`
for its next `/refresh`.

🔴 **ONE DECISION STILL NEEDED FROM MALIK BEFORE THE KEY GOES ON PRODUCTION: WHICH KEY.** The only
key touched so far is **Thrive Timesheet's**, borrowed for verification. Putting it on Martin's
production would bill another project for a client demo, make the spend unattributable, and mean
revoking it breaks Thrive. **Martin's demo needs its own Anthropic key.** Not resolved.

**Files changed (uncommitted):** `backend/app/config.py`, `backend/app/services/ai_client.py`,
`backend/app/schemas/procurement.py` (the two new fields, or the API would silently drop them),
`docker-compose.demo.yml`, `docker-compose.yml`, `.env.example`, new `backend/tests/test_ai_caps.py`,
`ERROR_LOG.md`, `_state/open-items.md` (OI-92), this file.

## 🟢 2026-08-26 (evening). THE REST OF MARTIN'S SCOPE IS BUILT AND VERIFIED LOCALLY. NOT YET DEPLOYED — waiting for the UK shop to close.

**Every remaining item in FZ LLC's written scope is now built.** Procurement, OCR receiving, the
AI ordering advisor and back-office quotations. All verified end to end against the real API
through nginx, not only by unit test.

🔴 **NOT DEPLOYED. Local only.** `git push origin main` recreates the SHARED nginx serving Chick
Shack's tablet, and the UK shop opened during this session. **Deploy after close, and take the
Chick Shack baseline immediately before.**

**Shipped in this session (local):**
| Block | Verification |
|---|---|
| Supplier master, catalogue, purchase history | **45/45 live API checks** |
| PO workflow: draft → send → receive → stock, partial + over-delivery, email sending, printable A4 PO | same run |
| Ordering engine: production target → recipe explosion → what to buy | **35/35 live checks**, arithmetic hand-worked from the seed |
| OCR goods receiving | **42/42 live checks with REAL model calls**, PDF and photo |
| Back-office quotations: raise → send → win/lose → convert to order | **33/33 live checks** |
| Regression tests | 67 new (30 + 16 + 21). **Full suite 736 passed**, same 10 failed + 2 errors as clean HEAD |
| Migrations | 3 new, entirely additive, each upgrade/downgrade/upgrade round-tripped |

**Three real bugs found by end-to-end runs that the unit tests missed** (all in `ERROR_LOG.md`):
a stale eager-loaded collection made a just-written goods receipt invisible to its own request
(`populate_existing`); a magnitude assertion passed on a zero total and proved nothing; the
frontend `Ingredient` type had been missing `is_produced` since the sub-recipe work shipped.

📌 **AI design decision worth keeping.** The ordering quantities are **computed, not generated** —
the recipe explosion is arithmetic and a model never touches a number that lands on a purchase
order. The AI reads the finished plan and adds judgement it cannot act on. OCR likewise only ever
**proposes**; a human confirms through the same receiving endpoint manual entry uses. Both
features are opt-in and the system is fully functional with no API key at all.

📌 **`api-cost-playbook` applied, not improvised.** Instrumentation first (`ai_usage_log`, one row
per call with its four token classes), one model constant, cached system block, the B1 rule (the
model gets a compact numbered allowlist and answers with indexes, never the ingredient master),
per-tenant daily caps that degrade gracefully, and an admin usage endpoint. **Prompt caching
confirmed live, not assumed: 1,563 tokens written once, 3,126 read back across the next two
calls.** Measured cost ≈ **$0.026 per delivery-note scan** on `claude-opus-5`.

⚠️ **The AI key used for verification is Thrive Timesheet's**, read from that project on Malik's
instruction for testing only. **Production has no key**, so OCR and the advisor are OFF there
until one is set. Everything else works without it.

**Deliverables written** (in `_context/clients/fz-llc-uae/proposal/`, Markdown source + PDF):
demo recording shot-list, client system-walkthrough/UAT playbook, and the two-tier proposal with
the integration playbook and payment-gateway comparison.

🔴 **The proposal is NOT committed, deliberately. `github.com/mallikamin/POS-System` is PUBLIC and
`_context/clients/` IS tracked.** Committing it would publish Sitara's pricing, the margin
reasoning, and a live client negotiation. Left unstaged pending Malik's decision. Note this is a
pre-existing exposure, not a new one: Chick Shack's discovery notes, meeting transcripts and
discount analysis are already public in that repo.

⚠️ **The proposal's numbers are DRAFT** and carry an internal "remove before sending" block.
Malik has not approved them. The one tension flagged for him: the Tier B e-commerce delta of
AED 120/month is below the Chick Shack precedent (£35/mo) for comparable functionality.

**Still untracked and must stay that way** (plaintext credentials, public repo):
`backend/app/scripts/{system_admin,sync_system_admin,seed_fz_llc,seed_demo_kitchen}.py`, plus the
four new verification scripts that import from them —
`verify_procurement.py`, `verify_suggestion.py`, `verify_ocr.py`, `verify_quotations.py`.
**They are the verification evidence for this session; do not lose them.**

## 🟢 2026-08-26 ~11:45 UK. BOTH FZ LOCATIONS ARE LIVE AND VERIFIED ON PRODUCTION (`815a21e`). Chick Shack byte-identical through two deploys.

**Martin's demo link: `https://eats.sitaratech.info/login?shop=martin-fz`.** Credentials in
`backend/app/scripts/seed_fz_llc.py` (`ADMIN_USER`), not repeated here.

📌 **Deadline corrected on Malik's instruction: the real target is FRIDAY 2026-08-28**, not
Monday. Build + UAT + fixes done Friday, link and proposal to Martin so he and his partners review
over the weekend, reconnect Monday 08-31.

**The two locations, exactly as described on the call:**
| | Location 1 | Location 2 |
|---|---|---|
| Name / code | Production & Wholesale (PROD) | Delivery Kitchen (DEL) |
| Type | production | delivery |
| Billing | **A4 VAT tax invoice**, legal name `FZ LLC`, TRN `100123456700003` | thermal ticket |
| Stock | 15 ingredients incl. 3 produced sub-recipes | 3 ingredients |

**Shipped in `815a21e`** (migration `x0y1z2a3b4c5`, entirely additive): `locations`,
`location_stock`, `sales_channels`, `stock_transfers`, `stock_transfer_items`; `orders` gained
`location_id`, `sales_channel_id`, `channel_commission_minor`; `inventory_transactions` gained
`location_id`. Five new services (stock, production, transfer, location, tax invoice), 20 new API
routes, **seven new admin screens** plus sub-recipe support in the recipe builder.

🟢 **VERIFIED ON PRODUCTION THROUGH THE PUBLIC URL, 43 checks, all passing** (not the internal
network, not the test suite): both locations returned; stock scoped per site and isolated;
low-stock alert fires on the seeded Espresso Beans shortage; a production run consumed 6 inputs and
raised Croissant Dough 15 to 25 kg; a transfer created, sent, received, and correctly refused a
second receipt (400) and a same-location transfer (422); profitability breaks down by all 6 channels
and both sites; and the A4 tax invoice returns with the legal name, TRN, sequential number
`FWZ-00002`, VAT shown separately and lines reconciling to the total.

📌 **The number that makes Martin's own case for him: Talabat nets 66.25% margin against
80.2% direct.** That ~14-point gap is exactly what he said off-the-shelf reporting hides, and it is
now visible in the demo data.

🔴 **THREE REAL BUGS FOUND AND FIXED while building. All three were invisible to the test suite:**
1. **`InventoryTransaction.transaction_date` was missing `DateTime(timezone=True)`** - every stock
   movement would have failed against Postgres. Never hit only because no tenant had ever held
   stock. Same class as the `recipes.effective_date` bug. **A scan of all 33 datetime columns found
   no others**; `StockCount.count_date` is correctly a `Date` and was deliberately left alone.
2. **The recipe LIST endpoint did no enrichment at all**, so every recipe reached the UI unlabelled.
   Four duplicated inline blocks collapsed onto one helper that also names sub-recipes.
3. 🔴 **Product cost was multiplied by 100 in the profitability report.** `cost_per_serving` is
   already in minor units. This overstated cost 100x and produced margins of -1790%. **The unit test
   had the same wrong assumption baked into its fixture, so only end-to-end verification against the
   real API caught it.** Lesson worth keeping: a test written by the same person who wrote the bug
   will happily agree with it.
📌 Also found: **`IngredientManagementPage` and `RecipeBuilderPage` were commented out of the
router** since BOM Phase 3, so the whole inventory UI was unreachable. That is *why* a
Postgres-only bug survived a "100% complete" status. Both are now routed.

**Chick Shack, measured before and after BOTH deploys and the seed, never assumed:**
227 orders, newest `2026-08-25 20:03:19.780197+00`, 172 customers, 222 payments, **0 locations** (it
is single-site and stays that way). All four hostnames return 200 each serving its own certificate.
Orbit containers untouched. Only backend log output is the known trapped `bcrypt.__about__` noise.

**Rollback:** `/root/backups/pos_system_20260826T114101Z_pre_fzllc.sql.gz` (42 tables, footer
verified), images tagged `pos-system-backend:pre-fzllc` / `pos-system-frontend:pre-fzllc`, migration
`x0y1z2a3b4c5` has a tested `downgrade()` (upgrade, downgrade, upgrade round-trip verified locally).

⚠️ **STILL NOT BUILT, and must not be oversold to Martin:** supplier master + PO workflow +
email PO sending; OCR goods receiving; AI-assisted PO quantity suggestion; Tier-B e-commerce; and
**the two-tier written quote itself**, which is the actual deliverable Martin asked for.

🟢 **Universal system-admin now applied to ALL FOUR production tenants** (chick-shack,
cosa-nostra, demo-restaurant, martin-fz) on Malik's instruction, after a read-only pre-flight
confirmed no PIN collision would lock any staff member out. Verified by live login, password AND
PIN, on every tenant. Supersedes the "NOT applied to production" note below.

## 🟢 2026-08-26 ~10:32-10:50 UK. FZ LLC DEPLOYED TO PRODUCTION (`902e35f`). `martin-fz` IS LIVE ON `eats.sitaratech.info`. Chick Shack verified byte-identical before and after. Tenant isolation PROVEN, not assumed.

📌 **DECISION, Malik 2026-08-26, overriding an earlier plan of mine:** **one host serves every
tenant** — `eats.sitaratech.info` with `?shop=<slug>` — **not a subdomain per client.** A subdomain
per tenant would mean DNS + cert + nginx block + a deploy for every new client, which does not
scale. `sitaratech.info` is **Sitara's own domain** (`chickshackg84.com` is Imran's); an earlier
note in this session wrongly framed `eats.` as "Imran's URL" and that framing is **withdrawn**.
📌 Consequence: **no DNS record, no new certificate and no nginx config change were needed**,
which removed the single riskiest part of the plan outright.

**Martin's demo link: `https://eats.sitaratech.info/login?shop=martin-fz`.** Credentials are in
`backend/app/scripts/seed_fz_llc.py` (`ADMIN_USER`) — deliberately **not** repeated here.

**Rollback assets, all verified, all still on the box:**
- `/root/snapshots/fzllc_pre_deploy_20260826T100702Z/` — nginx conf, compose file, `.env.demo`,
  mounts, cert list, container/image IDs, git state.
- DB dumps: `/root/backups/pos_system_20260826T100702Z_pre_fzllc.sql.gz` (pre-deploy) and
  `pos_system_20260826T103916Z_pre_seed_martinfz.sql.gz` (pre-seed). Both size-checked **and**
  footer-checked for truncation.
- Images tagged `pos-system-backend:pre-fzllc` / `pos-system-frontend:pre-fzllc`.

**Migration was REHEARSED before it went near production** — the standard worth keeping. The real
production dump was restored into a local scratch DB (`pos_rehearsal`) and `w9x0y1z2a3b4` run
against it: applied cleanly on `v8w9x0y1z2a3`, chick-shack's 227 orders / 172 customers /
222 payments unchanged, all three constraints created, no model-vs-DB drift.
📌 **The reason it was safe is worth recording: `recipes` and `ingredients` were EMPTY on
production for every tenant**, so the new `ck_recipe_exactly_one_target` check constraint had no
existing row it could reject. Verify that again before any future constraint-adding migration.

**Chick Shack, measured before and after, not assumed:**

| | Baseline 10:07 | After deploy + seed |
|---|---|---|
| chick-shack orders | 227, newest `2026-08-25 20:03:19.780197+00` | **identical** |
| customers / payments | 172 / 222 | **172 / 222** |
| menu_items (all tenants) | 338 | 342 (+4 = martin-fz's own) |
| Orbit containers | up | untouched, up 2-4 months |

All four hostnames returned **HTTP 200 each serving its own certificate**: `eats.sitaratech.info`,
`pos-demo.duckdns.org`, `orbit-voice.duckdns.org` and `parkcity.sitaratech.info`.
⚠️ **The deploy workflow only checks the first three** — `parkcity` (Orbit's) was checked by hand.
Worth adding to `deploy-production.yml`'s verify loop.

🟢 **TENANT ISOLATION PROVEN ON THE LIVE PUBLIC PATH** (not the internal network, and not asserted
from the architecture). Martin's real token, through nginx:
- `/customers/search?phone=07` — a term matching **101 real chick-shack phone numbers** — returned
  **0 rows**. Broadest probes `7` and `1` also **0 rows**.
- Foreign record IDs → **404**. His menu returns his own 4 items, orders **0** (not 227).
- **Martin's credentials on `chick-shack` → 401 rejected.**
- Unknown slug → generic **401**, so tenant names cannot be enumerated.
- ⚠️ Two earlier "failures" in this run were **my test being wrong**, not the system: a `405`
  (bare GET on `/customers`, the route is `/customers/search`) and a `422` (param is `phone`, not
  `q`). A **429** also appeared once — nginx rate-limiting the login endpoint under repeated
  probes, which is why the re-test backs off. **Do not read a 429 there as an auth result.**

⚠️ **Universal system-admin is STILL NOT on production chick-shack** — verified live, it returns
**401** there while working on `martin-fz`. Unchanged from the checkpoint; needs Malik's explicit
go-ahead as its own step.

🔴 **NOT VERIFIED, and it is the exact shape of the Meta-review failure: nobody has opened the
demo in a browser.** The API is proven end to end and `/login?shop=martin-fz` serves the SPA shell
(HTTP 200), but **that the page renders and the login form works visually is UNTESTED** — there is
no browser tooling in this environment (see [[no-claude-in-chrome]]). **Someone must click the link
before it goes to Martin.**

📌 **Two operational lessons from this deploy, both new:**
1. **The backend container has a read-only rootfs**, so `docker cp` into it fails. To run a one-off
   script against production, build a throwaway image `FROM pos-system-backend` with
   `COPY --chmod=644` (mode matters — the container runs as non-root) and
   `docker run --rm --entrypoint python --network pos-system_default --env-file .env.demo`.
   The image's own entrypoint runs migrations then uvicorn, so **`--entrypoint python` is required**
   or the module argument is swallowed by uvicorn.
2. **The seed scripts are deliberately NOT in git.** `system_admin.py` and `seed_fz_llc.py` hold
   plaintext passwords and **this repo is public** — they live at `/root/fz-scripts/` (mode 600)
   on the server and in the local working tree only. Keep it that way.

🔴 **SEPARATE FINDING, RAISED AND NOT ACTED ON (Malik's call): `github.com/mallikamin/POS-System`
is a PUBLIC repo and `.env.demo` is committed to it** (present in the `50a8002` tree, 3 commits of
history, not gitignored). `docs/DEPLOYMENT_PLAYBOOK.md:124` describes that file as carrying live
credentials. Contents were **not** read — the cred-guard hook blocked it and was not worked around.
📌 Note that flipping the repo to private is **not** a free click: if the server's `git pull`
authenticates over HTTPS it would break the deploy pipeline. Check that first.

## 🔴 2026-08-26. FZ LLC (Martin Zubeldia, UAE) — NEW LEAD, HARD DEADLINE MONDAY 2026-08-31. Core technical ask BUILT AND VERIFIED locally; the client-visible demo URL is the blocker and it collides with Chick Shack's deploy pipeline.

⚠️ **This entire session was missing from STATE.md until this refresh.** Sources reconciled:
`PAUSE_CHECKPOINT_2026-08-26.md` (authoritative for what was done) and
`_context/clients/fz-llc-uae/plan-and-todo_2026-08-26.md` (authoritative for what remains).

**Who/what:** prospective UAE client, contact **Martin Zubeldia**, bakery/cafe, **delivery-only, no
dine-in, 2 locations** (production/B2B + delivery-only). Wants POS + Inventory + Procurement +
multi-layer recipe/sub-recipe production + OCR goods receiving + AI-assisted PO suggestions +
per-channel net-profit reporting. Commercial anchor: **near-zero upfront + flat 225 AED/month
all-inclusive**, two-tier quote (with / without e-commerce). Standing directive from Malik verbatim:
**"I need the complete thing. No half-cooked jobs."**

🟢 **Built and verified 2026-08-26 (local dev only, `localhost:8090`, nothing client-visible):**
- **Multi-layer sub-recipe production chain** — migration `w9x0y1z2a3b4`: `recipes.menu_item_id` now
  nullable, new `recipes.produces_ingredient_id`, DB check constraint enforcing exactly one target,
  `ingredients.is_produced`. `recipe_service.sync_produced_ingredient_cost` rolls a sub-recipe's cost
  onto the ingredient it produces, so raw → sub-recipe → intermediate → final costs roll up
  automatically. 4 new tests in `backend/tests/test_recipe_service.py`, all passing.
- 🔴 **A real pre-existing bug was found and fixed on the way:** `Recipe.effective_date` and
  `StockCount.reviewed_at` were missing `DateTime(timezone=True)`, so **any** recipe creation against
  Postgres failed with an asyncpg tz mismatch. The test suite is SQLite in-memory and cannot catch
  this class of bug. **This is why `BOM_IMPLEMENTATION_STATUS.md` said "100% Complete" wrongly** —
  recipe creation had never been exercised against Postgres. Correction note added to that file.
  Full writeup in memory `recipe-module-tz-bug-and-test-gap.md`.
- **`martin-fz` demo tenant seeded** (`backend/app/scripts/seed_fz_llc.py`, idempotent): AED, 5% VAT,
  no floors/tables, 3 categories, 4 menu items, 12 raw ingredients, 3 sub-recipes, 4 final recipes.
  Verified through the **real HTTP API**, not just the seed script's prints. ⚠️ The page render was
  **never visually checked** — no browser tooling in that session.
- **Universal system-admin login** — `backend/app/scripts/system_admin.py` is now the one canonical
  definition of Malik's own `malik@sitaratech.info` identity (create-or-sync, self-healing).
  ⚠️ **Applied to LOCAL DEV ONLY** (`chick-shack` + `martin-fz`). **NOT applied to the live
  production Chick Shack server** — needs Malik's explicit go-ahead as a separate step.
- Backend regression after the work: **620 passed**, 10 failed + 2 errors, all pre-existing (parked
  QB-Desktop suite + 2 bcrypt/passlib venv failures) and already documented as failing at clean HEAD.
- Local dev DB backed up pre-migration:
  `_files/2026-08/2026-08-26/pos_system_20260826_pre_fzllc_recipe_migration.dump` (251KB, verified).

🔴 **NOT done, and this is the real remaining deliverable — do not oversell any of it:**
demo URL · admin UI for building a sub-recipe · 2-location model + inter-location transfer ·
per-channel commission % and net-profit-by-channel reporting · A4 VAT tax invoice + back-office
quotations · supplier master + PO workflow + email PO · OCR goods receiving · AI-assisted PO
quantity suggestion · Tier-B e-commerce site · **the two-tier written quote itself**.

🔴 **THE BLOCKER, and the thing that makes this a Chick Shack risk event.** Everything above runs
only on `localhost:8090`. Standing rule: **never hand `pos-demo.duckdns.org` to a client.** Putting
`martin-fz` on a client-visible URL on the shared droplet means **all three** of the following, each
of which touches live Chick Shack infrastructure — this was verified against
`docs/DEPLOYMENT_PLAYBOOK.md` and `docker/nginx/nginx.demo.conf` on this refresh, not assumed:
1. **`git push origin main` IS the deploy.** It rebuilds backend **and** frontend and recreates
   **nginx** — the same nginx serving `eats.sitaratech.info` (Imran's live order tablet),
   `pos-demo.duckdns.org`, `orbit-voice.duckdns.org` and `parkcity.sitaratech.info` (Orbit's, not
   ours). There is no way to ship the backend without recreating shared nginx.
2. **The pipeline runs `alembic upgrade head` on the production DB.** Migration `w9x0y1z2a3b4`
   would execute against the database holding Chick Shack's real orders. The workflow does `pg_dump`
   first and aborts on an empty dump, but this is still the single highest-risk step.
3. **A new subdomain needs a new nginx `server` block + its own Let's Encrypt cert.**
   `parkcity.sitaratech.info` (lines ~417-455 of `nginx.demo.conf`) is the working precedent for the
   shape: an `:80` block for the ACME challenge plus an `:443` block with its own cert pair.
   ⚠️ A cert that does not exist yet means nginx **fails to start**, which takes down **both**
   Chick Shack and Orbit. Order of operations is not optional: DNS → issue cert → add block →
   `nginx -t` → recreate.
📌 **Also still true and unresolved:** HEAD `cd57170` is **1 unpushed docs commit**, and pushing it
alone re-runs the whole pipeline. There is no docs-only push on this repo.

📌 **Timing:** Chick Shack closes **22:00 UK**. `scripts/deploy_after_close.sh` exists for exactly
this. Any push should be timed to a closed-shop window unless Malik explicitly says otherwise.

⚠️ **Minor contradiction found and recorded rather than silently merged:**
`PAUSE_CHECKPOINT_2026-08-26.md` claims a `.txt` call transcript was produced alongside the video.
**No `.txt` exists** in `_context/clients/fz-llc-uae/voice-notes/` — only the 1.04 GB `.mp4`
(gitignored via `.gitignore:96`, so no repo bloat). The call's content **is** captured in
`discovery.md` and `plan-and-todo_2026-08-26.md`, so nothing is lost, but the transcript file itself
is gone and would need regenerating (faster-whisper, local) if the raw wording is ever needed again.

## 🔴 2026-08-25. OI-91 OPENED, FB LIVE ON THE CHICK SHACK PAGE IS BLOCKED BY META'S OWN ELIGIBILITY GATE, NOT BY OUR STACK.

**Ask (Malik, 2026-08-25):** now that Page access is granted, run a 24/7 FB Live on the Chick Shack
Page the same way GN/UPN do it from the Tailscale edge box; creatives to follow, Imran to approve.
Third-party report carried in: *"ccbw bilal waheed couldn't get it done because page had to be 2
months old."*

🟢 **That report is CORRECT and it is now verified at source.** Meta Help Centre
`facebook.com/help/587160588142067` ("Go live on Facebook using streaming software") states three
requirements: (1) **the account must be at least 60 days old**, (2) **the Page or professional-mode
profile must have at least 100 followers**, (3) **Facebook access or task access** to create content.
Fetched 2026-08-25; the page rendered in Urdu on our locale but the three clauses are unambiguous.
📌 This is the **streaming-software / Live Video API** path specifically, the same path
`stream.py` uses. Going live from the phone app is a different, laxer surface.

🔴 **Chick Shack fails clause (2) today: the Page has 58 followers** (read off the live Page
on the 08-25 pass, recorded below). 58 < 100.

🟢 **Clause (1), the 60-day age gate, is CLEARED.** Malik's screenshot (2026-08-25) shows a
Page post by `Imran Rasul` dated **May 14** with no year, i.e. **2026-05-14**, which is **~103 days
before today**. A post on that date proves the Page existed then, so the exact creation date does not
matter: it is a lower bound comfortably past 60 days. Malik's own personal account, the one that
would carry the stream, is years old on either reading of "your account".

🔴 **CORRECTION to a claim made earlier in this same session.** This file said Page age was
"inferred-young" from 58 followers, the ~2w-old "ONLINE ORDERING IS NOW LIVE" post, and every
full-control admin being added inside the last week. **That inference was wrong.** Recent *admin*
adds and a low follower count say nothing about *Page* age, and the Page is at least 3.4 months old.
Recorded rather than silently edited because the wrong version briefly made this look like a
two-clause block.

Clause (3) **we already satisfy**, our grant is task-level `Content, Messages and
calls, Community activity, Ads, Insights`, and task access is explicitly sufficient.

📌 **Net: exactly ONE clause is left, and it is a number. 58 followers, need 100.**

📌 **So the blocker is a follower count, not an architecture problem.** Nothing needs
building or proving on our side to unblock it; the Page needs +42 followers and probably some
calendar time. Do not spend build effort on the stream until the count clears 100.

**The GN architecture, for the record (verified from source, not memory):**
`C:\FBAI\desktop\LiveTTAgent\winlive\stream.py` (436 lines, Windows original) → ported to
`/opt/livett` + `/opt/upn-live` on **loom-edge-01**, the IT-room Ubuntu Server box on the tailnet at
`100.119.110.37`. Per session: resolve the Page token from the canonical
`goldennummbers\config\config.json` (rotated by `tools/rotate_fb_token.py`) → `POST
/{PAGE_ID}/live_videos` asking for `id,permalink_url,secure_stream_url`, with a 6-retry DNS-blip
guard → **ffmpeg loops a pre-rendered `live_loop.mp4` + `audio/voiceover.mp3` with `-re`** at
`VIDEO_BITRATE=2500k` → pushes **RTMPS** to `secure_stream_url` → auto-posts and pins the CTA comment
→ runs `STREAM_DURATION_SEC` (**28800 = 8h**, deliberate session rotation) → ends and optionally
deletes the `live_video` (`DELETE_ON_END`). `build_loop.py` regenerates the mp4 on a daily 06:00 PKT
cron. systemd units `livett-stream` / `upn-live-stream`, `Restart=always`, SIGTERM teardown so a
clean stop ends the live_video properly. `fleet-monitor.sh` watches both units.

**Both GN streams are off today because WE turned them off**, deliberately and manually:
`livett-stream` on 2026-07-07 (Malik chose pause over harden) and `upn-live-stream` on 2026-08-17
in the brand pause. Neither was stopped by Meta, and both resume with
`systemctl enable --now <unit>`. **The encoder capacity is free, which helps rather than hurts
this idea.** Do not read the "off" state as a warning sign.

📌 **The one thing worth carrying across from GN:** the classifier signature that got the
number-board VODs removed was *number grid + solicitation CTA*, which food content does not have, so
this is **not** a reason to refuse. The
part that **does** carry over is the **24/7 identical loop**, which is a spam signal in its own
right independent of subject matter. If we build this, the GN lessons already paid for are: short
scheduled windows rather than 24/7, `DELETE_ON_END=1` so no permanent re-scannable VOD accumulates,
no repeated identical pinned CTA comment, and vary the board.

**Also binding on this idea, carried from elsewhere in this file:** Instagram is **not linked** and
is gated until ~2026-09-01; and the storefront still has **no pixel** (`fbq`/`gtag`/`dataLayer` all
zero at the 08-08 diagnosis, unchanged), so a live that drives orders would be **unmeasurable**,
same as ads.

**Next action on OI-91:** nothing to build, and nothing left to verify. **The only task is getting
the Page from 58 to 100 followers.** Creatives and Imran's approval come **after** that, not before,
because a rejected creative for a stream we cannot legally start is wasted work on both sides.

## 🟢 2026-08-25. OI-72 SOCIAL HALF DONE AND VERIFIED BY EFFECT. Imran granted Page access, Malik accepted, and the full **Manage Page** admin view renders on Malik's own account. Ads are now blocked by ONE thing, not two.

🔴 **CORRECTION, made within this same refresh. The first read of his screenshots was wrong.**
On first sight of `business.facebook.com/latest/settings/profiles?asset_id=1176900818828909` listing
three Pages (Supra Cleaning Services, Supra Security Ltd, Chick Shack) this file recorded
"a portfolio exists, id `1176900818828909`". **That was an over-read of an `asset_id` in a URL.**
Two further screenshots refuted it and the corrected reading is below. Recorded rather than silently
edited, because the wrong version briefly drove the plan.

**What his screens actually show, and the two tests that settle it:**
1. **The settings surface has no people-management sections at all.** Malik's own Rang Rasiya
   portfolio (the walkthrough he was screenshotting) shows **People / Partners / System users /
   Accounts > Pages / Ad accounts / Business asset groups**. Imran's shows a three-icon rail and a
   flat **Profiles** list. A real business portfolio cannot render without People and Partners.
   His screen is the **personal-account** "pages I manage" list.
2. **The Profiles rows are a profile SWITCHER, not a drill-in.** Clicking `Chick Shack` lands on
   `business.facebook.com/latest/home?asset_id=1176900818828909` with `Chick Shack` selected in the
   top-left switcher: Business Suite Home for the Page, no permissions pane. Malik, 08-25: *"its a
   loop. he clicks on settings it shows that page he clicks on chick shack redirects on the same
   window."* The `asset_id` never changing across both views is the selected-profile context, not
   proof of a container.

📌 **Consequences:**
1. **Unverified item (3) from 08-08 is answered: NO portfolio exists.** The 08-20 plan's clean
   "Partner-by-Business-ID" route and the "Assign people" route **both require a portfolio he does
   not have**. The Rang Rasiya walkthrough screenshots are therefore **not usable for him** - the
   exact failure mode flagged on 08-20 ("sending portfolio-shaped screenshots to a man with no
   portfolio wastes his one laptop session") is what happened.
2. 🟢 **His advertising restriction did NOT fire.** He reached Business Suite Home for the
   Page with no error popup and no "temporarily restricted" dialog. His *"Doesn't allow me to"*
   (00:12) was **navigation confusion, not a block**. That is materially better news than the 08-20
   prediction assumed, but note it only clears the *Page* path; the ads restriction itself is
   untested and unchanged.
3. **The route is Page-level access via the Page's own Professional dashboard**, which needs no
   portfolio and is the path least exposed to a "managing people for businesses" restriction.
   ⚠️ **Unverified on his build** - the exact label and whether the field accepts an email
   rather than a profile name has not been seen on his screen yet.
4. Building him a portfolio from scratch stays a **fallback, not the plan**: it is heavier and it is
   precisely the "managing people for businesses" action his restriction names.

**Other facts read off his screens, minor:** Chick Shack has **58 Facebook followers**; Instagram is
**not connected** to the Page ("Connect Instagram" still showing), which matters because social
management was scoped to include IG; a regional-privacy alert limits some Inbox/messaging insights;
his most recent Page comment activity is the *"ONLINE ORDERING IS NOW LIVE"* post from ~2w prior.

⚠️ **BLOCKER RAISED THEN REFUTED 2026-08-25, inside the same session. Recorded in full
because the wrong version briefly drove the plan toward a portfolio build.**

🔴 **What was claimed (WRONG):** that the Page-level screen has NO email field and granting
by email is Business-Manager-only.
🟢 **What refuted it:** Imran opened `Add new` and the dialog reads
*"Who should have Facebook access to this Page?"* over a field labelled
**"Search by name or email address"**. **The Page-level flow accepts an email.** Imran's
*"You need to be on my friend list to add you on"* was **his assumption, not a UI constraint**, and
it was taken at face value for one step. ⚠️ Still unverified: whether an email that is not
a friend actually **resolves** (Facebook's "who can look you up by email" privacy setting can block
it). **The portfolio detour (Route A) is off unless the lookup fails.**

📌 **Receiving-account rule bent, deliberately, by Malik.** Malik, 2026-08-25: *"my account
is associated with malik.amin187@gmail.com"*, i.e. **`amin@sitaratech.info` has no Facebook profile**
- it is a Business Manager invite address only. Since the Page flow searches Facebook profiles, the
standing `sitara-meta-receiving-account` rule (*never the personal account*) **cannot be satisfied on
this route**. Flagged to Malik; he proceeded. Access is therefore landing on the **personal profile
`malik.amin187@gmail.com`**. 📌 **Revisit if a portfolio is ever created** - move it to
`amin@sitaratech.info` then.

⚠️ **Tier note:** the dialog Imran opened is **People with Facebook access** (full control),
not **People with task access**. Plan is to proceed there and switch **Page deletion** and
**Permissions** OFF on the permissions screen that follows.

**Superseded detail, kept for the trail:** Imran reached `facebook.com/settings/?tab=profile_access` (route:
Professional dashboard -> All tools -> Profile -> **Page access**) and reported: *"You need to be on
my friend list to add you on"*. **He is right, this is not user error.** On the New Pages Experience
Page-access screen, both **People with Facebook access** and **People with task access** resolve
people by searching the Page admin's **Facebook friends**. Granting by **email address** is a
**Business Manager** mechanism, not a Page mechanism.

📌 **This also corrects the reasoning behind the `amin@sitaratech.info` rule.** Rang Rasiya
worked on that address because it was a **Business Manager invite**, where the email is an *invite
address* the recipient accepts with whatever Facebook account they hold. It is **not** evidence that
`amin@sitaratech.info` is a searchable Facebook profile. ⚠️ **Whether a Facebook profile
exists on that address is UNKNOWN and is the question the route now hinges on.**

**Two routes, put to Malik 2026-08-25, undecided at time of writing:**
- **Route A, portfolio (no friending).** Imran creates a business portfolio, adds the Chick Shack
  Page to it, invites `amin@sitaratech.info` by email. Same mechanism as Rang Rasiya, and it is the
  structure ads need anyway. Costs: a structural change to a live Page, and 🔴 adding people
  to a business is **precisely** what his advertising restriction names ("can't manage advertising
  assets or **people for businesses**"). Untested. His restriction has not fired at any point tonight.
- **Route B, friend then task access.** Two minutes, works immediately. Violates the standing rule
  that client assets never land on a personal profile - **unless** `amin@sitaratech.info` has its own
  Facebook profile, in which case Imran friends that and the rule's substance is respected.

**Read off the Page access screen, worth keeping:** ⚠️ **three accounts hold FULL
"Facebook access"** on the Chick Shack Page - `Imran Rasul (you)`, `Zeinab Rasul`, and a **second
`Imran Rasul` account** - each with `Page deletion, Permissions, Content, Messages and calls,
Community activity, Ads, Insights`. **People with task access is empty** apart from the
Community managers entry. Whatever we take should be **task access**, never Facebook access; we do
not need Page deletion or Permissions.

🟢 **GRANTED AND VERIFIED, 2026-08-25 ~00:34 UK.** Imran sent the invite from the Page-access
`Add new` dialog using **`malik.amin187@gmail.com`**; Malik accepted. **Verified by effect, not by
the invite mail:**
1. `facebook.com/malik.amin.9` -> profile switcher -> **"Your profiles & Pages"** lists **Chick
   Shack** (1 notification) alongside Sitara InfoTech, Telecom Store UAE, Golden Numbers UAE,
   Postpaid Plans, KS Consulting and others.
2. Switching in loads `facebook.com/chickshackuk/` with the **full `Manage Page` rail**:
   Professional dashboard, Insights, **Ad Center**, **Create ads**, Boost Instagram post, Settings,
   Meta Verified, Leads Center, Meta Business Suite, Nonprofit Manager, plus `Edit cover photo`,
   `Edit`, `Edit details` and a live composer.
3. ✅ **CORRECTION to a claim made minutes earlier in this same session.** The Manage Page rail
   looked like full control and was written up as such. **It is not.** Imran's own screenshot of the
   Page-access list (00:32 UK) shows Malik's row as **`Content, Messages and calls, Community
   activity, Ads, Insights`** with a red *"Deletion ... 30 days"* note, and **without `Page deletion`
   or `Permissions`** - which Imran's and Zeinab's rows both carry. **So the scoped set we wanted was
   granted by default**, and the earlier worry about holding deletion rights on a live client Page
   does not apply. Meta withholds deletion/permissions from newly added people for a waiting period.

⚠️ **A SECOND, UNIDENTIFIED PERSON was added at the same time.** The list now holds five
people. Directly under Malik's row sits **`Sulem Javaid`** (spelling uncertain, read from a photo of
a screen), with the **identical** permission set and the identical 30-day note - i.e. added in the
same window as us. **We do not know who this is.** It is not Sitara. 📌 **Ask Imran who it
is and whether it is intended** before any social work starts; an unknown account with Content,
Messages and Ads on a live Page is a real exposure, not a formality.

🔴 **INSTAGRAM IS BLOCKED, AND THE EXACT META RULE IS NOW ON RECORD.** Imran, 00:35 UK:
*"I need to wait 1 week to link Instagram account"*, from Business Suite. He screenshotted the
dialog verbatim:

> **You can't connect this Page yet.** You need to have **full control access of a Page for at least
> a week** before you can connect it to Instagram. **You can ask another person with full control to
> add it** or wait until your week has passed and you're eligible.

The Page is therefore confirmed **not** IG-linked; the `Boost Instagram post` entry in the Manage
Page rail is not evidence of a link, exactly as suspected.

📌 **Two things follow.** (a) **Malik cannot do this either** - he was added tonight and does
not hold full control at all, so the same rule bites harder. (b) **There is a documented way out the
dialog itself offers:** another full-control holder can link it. **Two other accounts already carry
`Page deletion, Permissions`: `Zeinab Rasul` and the second `Imran Rasul` account.** ⚠️
Whether either has held it for over a week is **unverified** - it is worth trying, not certain. This
also implies the account Imran was using **acquired full control recently**, which is itself worth
understanding.

🔴 **TRIED AND BLOCKED, 00:40 UK. The second `Imran Rasul` account is RESTRICTED.** He logged
into it and got the generic popup: *"Your account is restricted. You're temporarily restricted from
taking this action to protect your profile. Please try again later."* ⚠️ **This is the same
popup he hit on 2026-08-08 when he last tried to link Instagram** - so an IG link has now been
blocked twice by a Meta restriction, on two different accounts of his. Treat "his personal accounts
can link Instagram" as **disproven for both**, not merely untested.

🔴 **ZEINAB IS OUT TOO - NO ELIGIBLE ACCOUNT EXISTS. Imran, 00:44 UK:** *"Will need to wait
as zeinab account was added same time as the other new one."* So **every** full-control holder
acquired it inside the last week, which is consistent with the Page itself being only a few weeks old
(58 followers, the "ONLINE ORDERING IS NOW LIVE" post ~2w back). ⚠️ Note this is Imran's
own account of it - the Page-access list showed Zeinab **without** the red 30-day note that Malik's
and `Sulem Javaid`'s rows carry, so the two readings do not perfectly agree. **Taking Imran's word;
he knows his own Page. Not worth another laptop session to reconcile.**

✅ **DECIDED: hard wait to ~2026-09-01, and the agreed fallback runs meanwhile** - post to
Facebook and Instagram **separately** for the week, then connect once someone is eligible. **Nothing
further to try.** The Facebook half is live and working today; only the IG half slips.

📌 **Lesson worth carrying to the next client:** Meta's Instagram-link gate is
**per-person-per-Page and time-based**, so a brand-new Page whose admins were all added recently has
**nobody** who can link Instagram, no matter how many full-control accounts it has. Ask "how long has
someone held full control" **before** promising an IG start date.

⚠️ **One consequence to revisit:** the `sitara-meta-receiving-account` rule is **bent** -
access sits on `malik.amin187@gmail.com`, not `amin@sitaratech.info`, because the Page flow searches
Facebook profiles and that address has none. Move it if a portfolio is ever built. Nothing was posted
or edited during verification.

📌 **The ads picture has genuinely changed, and this is the most useful thing to come out of
tonight.** The 08-20 position was that ads were blocked by **two** things: (a) Imran's advertising
restriction, and (b) zero storefront measurement. **(a) is now routed around** - Malik holds Ad
Center and Create ads from his own clean account, so ads need not touch Imran's restricted profile at
all. 🔴 **(b) is untouched and is now the sole blocker**: `fbq`/pixel/`gtag`/`dataLayer` were
all zero at the 08-08 diagnosis and no storefront change has shipped since. **Do not start spend
before the pixel exists** - it buys an unreadable result. Also still binding: any portfolio that runs
this must be **dedicated to Chick Shack**, never the Etisalat portfolio `281900244999301`.

**Read off the live Page, useful for the social work and not previously recorded:**
`facebook.com/chickshackuk`, **58 followers, 0 following**, category `Meal Takeaway - Chicken Joint`,
address `Main St, Garelochhead, Helensburgh, UK`, phone `+44 1436 653143`, WhatsApp
`+44 7719 566889`, website **`chickshackg84.com`** (correct, matches the live storefront).
⚠️ **The Page has NO bio** ("Add bio" is empty) and nothing is Featured - both are free,
immediate wins. 🔴 **Instagram confirmed NOT linked and blocked ~7 days** (see above).

**NEXT (not started), in order:** (1) ~~ask Imran who `Sulem Javaid` is~~ - **DROPPED on Malik's
instruction, 2026-08-25.** Raised as an unknown account holding Content/Messages/Ads on the live
Page; Malik said drop it and stay on the Instagram thread. **Not investigated, not cleared** - if it
matters later, it starts from scratch. (2) write the Page bio (currently empty) in the
village-centric register from `_context/clients/chick-shack-uk/voice-of-customer.md`; (3) the
storefront pixel, now the **only** thing standing between here and ads; (4) re-attempt the Instagram
link on or after **~2026-09-01**.

🟢 **GOOGLE BUSINESS PROFILE ACCESS GRANTED AND VERIFIED, 2026-08-25 ~01:00 UK. Same night,
separate asset from Meta.** Malik, on Google: *"for google ads and gbp"*; Imran: *"On Google. What I
need to do"*.

**Route used (it worked first time, unlike Meta):** Imran opened the Chick Shack profile's
**People and access** panel directly from Google Search, clicked **Add**, invited
**`mallikamiin@gmail.com`** as **Manager** (not Owner). Malik accepted.

✅ **Verified by effect, not by the invite mail:** a Google search for `Chick Shack` from Malik's
account renders **"Your business on Google"** with the full manager toolbar - `Edit profile`,
`Read reviews`, `Photos`, `Posts`, `Performance`, `Edit menu`, `Food ordering`, `Waitlists`,
`Bookings`, `Ask for reviews`, `Profiles` - plus the knowledge panel badge **"You manage this
Business Profile"** and the footer **"Only managers of this profile can see this"**.

📌 **Receiving account decision, and it deliberately differs from the Meta one.** GBP went to
**`mallikamiin@gmail.com`**, not `amin@sitaratech.info`, on Malik's call: his existing GBP profiles
for **Sitara Infotech** and **goldennummbers** already live there, and splitting across two logins
means switching accounts on every touch. Unlike the Meta grant, **GBP manager access is removable in
one click with no waiting period**, so the separability argument is weak and a later move is cheap.

**Profile ownership:** primary owner is **`RB Dining Group`** (`rbdining.group.ltd@gmail.com`),
account group `am-919422655814423188`. Before Malik was added, that owner was the **only** person on
the profile.

📊 **Live numbers read off the profile, none of them previously recorded:**
- **5.0 stars, 17 Google reviews.** ⚠️ `_context/clients/chick-shack-uk/voice-of-customer.md`
  was built from **16**. **If the +1 post-dates 2026-08-22 it is the first conversion from the OI-90
  review QR** - which would matter, because OI-85 records the review *email* converting at zero.
  **UNVERIFIED: the review's date has not been read.** Check before claiming anything.
- **2,497 people saw the profile in search results last month**; **1,872 customer interactions**.
  Free, high-intent traffic already owned, larger than anything the storefront gets from ads today.
- **Profile strength is INCOMPLETE** ("Complete info"); Google is prompting for an **exterior photo**.
- Listed as `£1-10 - Fried chicken takeaway`, hours close 22:00.

🔴 **OPENED, and it may be the highest-value thing found tonight: the knowledge panel carries
`Order pickup` and `Order delivery` buttons above the fold.** Where they point is **unverified**. If
they route to an **aggregator**, every order through them pays commission on traffic Imran already
owns for free, and repointing them at **`chickshackg84.com`** is a pure margin win needing **zero ad
spend**. The `Food ordering` tool in the manager toolbar is what controls this. **Next action on the
Google side.**

🟢 **GOOGLE ADS ACCOUNT CREATED + CONVERSION TRACKING SHIPPED AND VERIFIED, 2026-08-25
overnight.** Third asset of the night, and the only one that involved a code change.

**Account:** **`758-817-4548`**, created by Imran from scratch (none existed). Malik holds
**Standard** access on `mallikamiin@gmail.com` (not Admin, not Billing - deliberately, so we can run
campaigns and never touch his payment details). ✅ Verified by effect: the account loads under
Malik's own login.

**Billing, Imran's own, we never see the card.** Business payments profile "Chick Shack", purpose
**Business** (needed for correct VAT invoices, cannot be changed later). Primary = **UK direct debit
`GB••…•2586`, mandate PENDING** (3-5 working days). Backup = **Mastercard
••••5881**, added because the DD alone left a *"New form of payment required -
your current payment methods can't be charged"* banner and nothing could run. That banner has now
cleared.

🔴 **The signup produced a PERFORMANCE MAX campaign, and it is deliberately left as an
unfinished DRAFT.** `Draft: Performance Max-1`, £3.00/day. Google's flow gives no choice.
**PMax is the wrong shape here:** no keyword control, effectively no negative keyword list, spend
sprayed across YouTube/Display/Gmail, and it is driven almost entirely by conversion history the
account does not have. It is also the answer to Malik's *"where do I add keywords, negative keywords
etc?"* - PMax has none. 📌 **Do not click Finish. Build a Search campaign instead.**
The draft costs nothing sitting there.

**Budget defence:** Google offered £8.50/day (£258/mo) as "recommended"; a custom
£3.00/day (£91/mo cap) was entered instead. Location auto-resolved to **8 miles of
Garelochhead**. ⚠️ **Promo with a deadline:** spend **£400 by 2026-10-24** unlocks
**£800 credit**. At £3/day he reaches ~£180 and misses it. Real money, but chasing it
means spending £400 fast. **Malik's call, explicitly deferred.**

### ✅ Conversion tracking: BUILT, DEPLOYED, VERIFIED ON PRODUCTION

**Conversion action:** `Purchase`, Primary, Website, **manual event snippet** (not auto-detect -
auto-detect keys off URL changes and the confirmation is a view swap on `/`, so it would never
fire). Click-through window cut from Google's default **90 days to 30**, because a takeaway order
happens the same evening and 90 days would credit ads for orders months later.
- Tag: **`AW-18408520125`** · Conversion: **`AW-18408520125/xy0DCPb1kOccEL3z7slE`**

🔴 **A UK PECR gap was found and closed on the way.** The storefront had **no cookie banner,
no consent handling and no privacy mechanism of any kind**. Dropping an ads tag in as-is would have
been a live compliance exposure for Imran's business. Built with **Consent Mode v2** instead:
`index.html` pushes `consent default: denied` for all four signals **before** gtag.js loads (verified
in the built artifact AND on the live domain - defaults at line 40, gtag.js at line 52), plus
`ads_data_redaction` and `url_passthrough` so a declined visit is still modelled.

**Files (storefront, Cloudflare Workers pipeline - NOT the backend `git push` pipeline):**
`index.html` (tag + consent defaults) · `src/lib/consent.ts` (new) ·
`src/lib/analytics.ts` (new) · `src/components/ConsentBar.tsx` (new) · `src/App.tsx`
(mounts the bar; ONE effect hung off `placed` fires the conversion, so **both** routes to the
confirmation - fresh order and Stripe return - count exactly once).

📌 **Decision to revisit: conversion value is the FOOD SUBTOTAL, not the total paid.**
Delivery fee largely passes to the driver and the tip is not the shop's, so bidding on the total
would systematically overvalue delivery orders and teach Google to chase the wrong basket.
Malik was told and did not object.

**Deployed** via `cd storefront && npm run deploy` (version `1f0c3d7c-cd0d-4435-b2db-123874a1356b`),
during the closed window. **Verified on the live domain with a browser UA, not on the Action.**

✅ **Verified by effect, in this order:** (1) consent bar renders on `chickshackg84.com`;
(2) tapping Allow and reloading keeps it gone, so the stored choice replays - the part that would
silently break for returning customers; (3) Tag Assistant reports **"This conversion action is
sending data to Google Ads"** with `Conversion value 1 GBP`, `Transaction ID TEST-001` and the
matching label.

⚠️ **What is NOT verified, stated plainly:** that event was fired **by hand from the
browser console**, not by the app. **Google receiving the event is proven; our confirmation screen
calling it, with the right value, on a real order is NOT.** Only the first genuine order proves that.
**Check the first real order's conversion in Google Ads before trusting any number.**
✅ The `Purchase` goal flipped from `Misconfigured / Inactive` to **`Active`** on the strength of
the manual test ping - so "Active" here means *Google has received data*, NOT *the app fires it
correctly*. Do not read it as the latter.

**NEXT on Google:** build the **Search** campaign (real keywords, negative list, tight radius),
leaving the PMax draft unfinished.

**Where we are in the WhatsApp flow (Malik driving, Imran executing):** Malik sent the Rang Rasiya
walkthrough (Settings -> Accounts -> Pages -> Assign people -> type the email). Imran replied he had
no laptop (08-24 20:12 UK), then at 00:10-00:12 got to Business Suite -> Settings and reached the
**Profiles** list, replying *"Doesn't allow me to"*. Malik replied *"wait"*. **Nothing has been
granted. `amin@sitaratech.info` has not been entered anywhere yet.**

**Next single step to send him:** click the **Chick Shack** row in that Profiles list, which opens
that Page's detail pane where people/permissions are assigned - and report whether he gets the pane
or an error popup. That one action both advances the handover and disambiguates point 3 above.

**Unchanged and still binding:** the receiving account is **`amin@sitaratech.info`** verbatim, never
the personal Gmail. **Friending is not the route.** Social media management is unblocked by Page
access alone; **ads are not** - his advertising restriction plus 🔴 zero storefront
measurement (`fbq`/pixel/`gtag`/`dataLayer` all zero at the 08-08 diagnosis). Do not read a
successful Page handover as ads being unblocked. Any portfolio that ends up running ads must be
**dedicated to Chick Shack**, never the Etisalat portfolio `281900244999301`.

## 🟢 2026-08-22 ~20:30-20:40 UK. OI-89 + OI-90 SHIPPED AND VERIFIED LIVE (`50a8002`). Deployed in service, tested by Imran on the shop printer, QR scanned from paper to the Google review form.

**Sequence, all verified by effect:** Imran approved the mockups (~18:00 UK). Built + 58 print tests
(byte-exact QR sequence, fold-in across cash/paid/fee/zero-tip, QR on every copy, no QR without a
URL); full suite **616 passed**, the 10 failures + 2 errors being the parked QB-Desktop suite and two
bcrypt/passlib venv failures that reproduce identically at clean `4b11c43` in a worktree. Snapshot
before deploy: backend image `866f26308068` tagged `pos-system-backend:pre-oi89`, env file backed up
on the box, `pos_system_20260822T172231Z_pre_oi89.sql.gz` (42 tables, complete footer), git tag
`pre-oi89`. Pushed 20:28 UK; server at `50a8002` after 2 min; backend healthy, started
`2026-08-22T19:30:27Z`; nginx recreated; 0 exceptions; Orbit untouched. A real tipped order
(`260822-D010`, £26.96 food + £2.00 tip) was rendered inside the production container first:
Subtotal £28.96, no Tip line, TOTAL £32.66, QR ×3.

**Imran's test, three slips photographed:**
1. First Print tap printed the OLD format. Not a deploy failure: the tablet caches one `rawbt:` URL
   per order in memory (`OnlineOrdersPage.tsx` `ticketUrls`, refetched only when `payment_status`
   changes), and D010's was cached before the deploy. 📌 **Rule for next time: any ticket-format
   change needs the tablet page reloaded after the deploy, or every already-listed order reprints the
   old bytes.** A plain reload, no hard refresh.
2. After reload: new format, printed by his printer. No Tip line, Subtotal/Platform Fee/Delivery/
   TOTAL, PAID ONLINE, review line, QR. **The native `GS ( k` QR command works on his printer**, so the
   raster fallback was never needed.
3. Phone camera on the slip's QR opened the **Chick Shack Google review form** (his screenshot,
   20:39). End to end on the real path.

**Rollback, not needed, stays available for a few days:** `bash scripts/rollback-backend.sh pre-oi89`
on the server (~30 s image swap, no build, no migration in this change), then `git revert`.

**Still true:** checkout, Stripe Tip line, emails and the reports tips tiles are unchanged. Tenants
with no `google_review_url` print no QR (only `chick-shack` has one; checked read-only). Imran was not
told about the Tips Act point in the 08-22 opening note; Malik's call whether to raise it.

### The opening note, kept for the audit trail (superseded above)


**Malik, 2026-08-22:** *"tips are being printed on the receipts which make riders keep [them]. imran wants
tips to be added in the subtotal and then the platform and delivery charges shown on receipt so its
not visible to the riders. checkout page stays same, just whats printed on receipts."* And: *"this is
eposnow receipt, it prints the QR code asking them for review on google, can we do the same on our
receipts too."* He wants HTML mockups first, Imran approves, then we deploy.

### OI-89, hide the tip on the printed ticket
**What prints today** (`print_service.py` money block, lines ~235-246): `Subtotal`, `Discount`, `Tax`,
`Platform Fee`, **`Tip`** (its own line, added by OI-81 on 08-14 precisely so the rider could see it),
`Delivery`, `TOTAL`, then `*** PAID ONLINE ***` / `*** CARD APPROVED ***` / `*** NOT PAID *** COLLECT £x`.
**Proposed:** `Subtotal` line = food subtotal **+ tip**; the `Tip` line is removed; everything else
unchanged, including the cash `COLLECT` total (which already includes the tip and must keep doing so,
or the rider under-collects). The cook list prints no prices, so nothing on the slip can be summed to
reveal the tip. **Touches nothing else:** `orders.tip` column, checkout, Stripe line, customer emails,
confirmation screen and the reports tiles all stay exactly as OI-81 shipped them.
⚠️ **One thing Imran should hear once, not a blocker:** the UK Employment (Allocation of Tips) Act
has applied since 1 Oct 2024 (tips must reach workers in full, allocated fairly, with a written
policy). Hiding the tip from the slip is a print choice; how the shop then distributes tips is his
obligation, not ours. The storefront makes no promise about where a tip goes (Malik cut the "goes to
your rider" line on 08-13), so nothing customer-facing is contradicted.

### OI-90, Google review QR on the printed ticket
**Proposed:** after the payment banner, `Scan to leave us a Google review` + a QR of the SAME URL
already held in `restaurant_configs.google_review_url` (used by the 08-10 review email), so reviews
from email and paper pool into one link. The printer's review link decodes were verified 08-09.
🔴 **Two things to settle before building, and both are Imran's to answer:**
1. **Does any copy of our slip reach the customer?** Today 3 identical copies print and "all three go
   to separate stations" (Imran, 08-01). A QR on a slip the customer never sees is wasted paper ×3. If
   one copy goes in the bag, fine; if not, the QR belongs on the EposNow receipt he already re-keys
   (OI-87) and prints, and this item closes with no code.
2. ⚠️ **UNTESTED: whether his printer renders a QR.** It is an unnamed "ESC/POS general" printer behind
   RawBT (`_state/printing.md`). Native `GS ( k` QR is standard on Epson-compatible units but has
   never been sent to this one. Build plan if approved: render the QR as a raster bitmap (`GS v 0`,
   supported by effectively every ESC/POS printer) rather than the native command, and give Malik a
   one-tap test print before it goes near a real order. `qrcode` 8.2 is installed locally; it is not
   yet in `backend/requirements.txt`.

**Mockups:** `_context/clients/chick-shack-uk/receipt-mockups_2026-08-22.html` (also published as an
artifact, link in the 08-22 session). Four proposed slips (delivery cash, delivery prepaid,
collection cash, collection prepaid) beside today's slip, using Imran's own OI-81 example
(£25.75 food + £3.50 tip, £0.70 platform fee, £3.00 delivery).

**Deploy path when approved:** backend only (`git push origin main` after the 22:00 UK close, or the
scheduled `scripts/deploy_after_close.sh`). No storefront deploy. Tests to add: the existing
print_service test file gets "no `Tip` line", "Subtotal includes tip", "COLLECT still = total", and a
QR-bytes-present case.

## 🔵 2026-08-20. OI-72 MOVED: Imran has offered to hand over Page access. His proposed method (friend request) is the wrong one, and the access he can actually grant may be narrower than he thinks.

**Malik, 2026-08-20:** *"imran is going to share his page access for us to handle social media and
ads. he was saying i should add him as friend and then he can share."*

**Friending is not required and should not be used.** In the New Pages Experience, Page access is
granted from Meta Business Suite by **email address**. Friend-based sharing is the legacy Page Roles
flow; it ties a business asset to a personal relationship and cannot be revoked cleanly.
⚠️ **This paragraph is from general Meta product knowledge, not verified against Imran's screen.
The screenshots in step 0 below are what verify it.**

**Precedent checked in the other projects, both routes, neither used friending:**
- `C:\FBAI\MEETING_CHECKLIST_ADEEL.md` step 5 (Rang Rasiya, 2026-02-27): *Business settings → Users →
  Partners → Add → enter App ID `1152633793482968` → grant the ad account "View performance"*.
  Partner-by-ID, no friendship.
- `etisalat-shop`: assets sit under the **Etisalat business portfolio `281900244999301`** and access
  flows through that portfolio plus system-user/app tokens. Again no friendship.
- `C:\FBAI\creatives\PROBIZ_META_AUTHORIZATION_LETTER.md`: the separate paper trail (a signed
  authorisation letter) used for Meta **Business Verification**, not for asset sharing. Different
  problem, do not confuse the two.

🔴 **The live risk, and it is the reason this cannot just be handed to Imran as a checklist.** The
2026-08-08 diagnosis on his personal profile lists *"can't manage advertising assets or people for
businesses"* among the restrictions. **Adding a partner to a business portfolio IS "managing people
for businesses".** So the clean Partner-by-Business-ID route is the one most likely to be blocked
for him, and it would fail with the same generic *"temporarily restricted"* popup he already saw
when linking Instagram. **Page-level access assignment is a Page task rather than a business-assets
task and is the more likely of the two to go through, but that is a prediction, not a verified fact.**

**Sequencing decided on this refresh: separate SOCIAL from ADS. They are not one handover.**
1. **Social media management** needs only Page access (+ the Instagram account linked to the Page).
   It is independent of every ads restriction and can start immediately once granted.
2. **Ads** stays blocked on two things that Page access does not solve: (a) Imran's advertising
   restriction, which means ads must run from a **clean ad account inside a dedicated portfolio**,
   and (b) 🔴 **the storefront still has zero measurement** (`fbq`/pixel/`gtag`/`dataLayer`: zero
   hits, re-confirmed at the 08-08 diagnosis). Spending before measurement exists buys an unreadable
   result. **Do not let a successful Page handover be read as "ads are unblocked".**

⚠️ **Portfolio hygiene, unchanged and still binding:** the restriction notice cites *"associating
with untrustworthy accounts"*. Any portfolio that takes on this Page must be **dedicated to Chick
Shack**. Never the Etisalat portfolio `281900244999301` that runs goldennummbers / postpaidplans.

### ⏸️ PAUSED 2026-08-20, mid-flow. Imran is at the restaurant with no laptop. Resume when he has one.

**Decided this session, not a guess:** the account that receives Page access is
**`amin@sitaratech.info`**, NOT `malik.amin187` / the personal Gmail. Reason given by Malik: that
address is the one **Rang Rasiya was shared on and it worked fine**. Use it verbatim when Imran
reaches the email field.

**Where we stopped.** Malik is inside **his own** `Rang Rasiya Business Manager` (Settings →
Accounts → Pages → `RANG RASIYA`, page ID `1078055745557087`) producing walkthrough screenshots to
send Imran. Last instruction issued: click **Assign people**. **The resulting panel was never seen**,
so the screenshot set is incomplete and nothing has been sent to Imran yet.

⚠️ **Risk flagged before the screenshots go out, and it is the thing to check first on resume: the
Rang Rasiya screen may not be the screen Imran sees.** Malik's view has `Assign people` /
`Assign partner` / `Connect assets` because that Page is **owned by a business portfolio he
controls**. If the Chick Shack Page sits on Imran's **personal profile with no portfolio**, those
buttons do not exist for him and the path is instead Business Suite → Settings → **Page access** →
`Add new`. **Which of the two he sees is exactly unverified item (3) from the 08-08 diagnosis (does a
business portfolio already exist).** Sending portfolio-shaped screenshots to a man with no portfolio
wastes his one laptop session.

📌 **First thing to ask Imran when he is at a laptop, before any screenshot is sent:** open
`business.facebook.com`, go to Settings, and say whether the left sidebar shows **Users / Accounts /
Data Sources** (portfolio exists) or only Page-level options (no portfolio). That single answer picks
the route and costs him 30 seconds.

**Still true and still binding:** social media management is unblocked by Page access alone; **ads
are not** (his advertising restriction plus zero storefront measurement). Do not read a successful
Page handover as ads being unblocked.

**Step 0, still the blocker, and it is 3 read-only screenshots from Imran on a laptop:**
(1) Meta Business Suite → Settings → **Page access**, showing who currently holds Full control;
(2) whether a `Request review` / `Disagree with decision` control still exists on his restriction
detail; (3) what `See accounts` lists, i.e. whether a business portfolio already exists for the shop.
**Nothing about the ads half can be decided without (2) and (3).** Nothing built, no ad spend, no
storefront change on this refresh.

## 🟢 2026-08-18 ~21:55 UK. IMRAN'S AOV HYPOTHESIS TESTED AGAINST THE REAL ORDER ROWS. It is directionally right and quantitatively wrong: fees explain about a QUARTER of the gap, not the gap.

**Imran, 08-18 ~21:36 UK (WhatsApp):** website AOV "doubles as the delivery charge and also the
platform fee is applied". He sent his EposNow Back Office ATV for both days alongside it, and said
the 18th was a slow day on the till too.

**Method: 17 rows read live from production `orders`, read-only**, 08-17 and 08-18, none rejected.
`aov_food_only = subtotal - discount_amount`, i.e. **delivery_fee, service_fee ("Platform Fee") and
tip all stripped.** Our `tax_amount` is 0 on every row (VAT-inclusive pricing, no separate line), so
no tax adjustment is needed. Gross figures reconcile to his own screenshot to the penny: 08-18 =
7 orders, £189.55, £27.07.

| | 17 Aug | 18 Aug |
|---|---|---|
| EposNow till ATV (his screenshots) | £14.59 (9 tx, £131.34) | £11.29 (13 tx, £146.75) |
| Website AOV as the dashboard shows it | £28.04 (10 orders) | £27.08 (7 orders) |
| **Website AOV, food only** | **£24.21** | **£23.09** |
| Fee + tip inflation | £3.83 (13.7%) | £3.99 (14.7%) |
| Gap to till, before | £13.45 | £15.79 |
| **Gap to till, after** | **£9.62** | **£11.80** |
| Share of the gap the fees explain | **28%** | **25%** |

🔴 **The hypothesis does not survive its own cleanest test: COLLECTION orders.** They carry **zero
delivery fee**, only the 70p platform fee. **6 collection orders over the two days average £20.12 of
food.** Against a till ATV of £11.29 to £14.59 that is still **1.4× to 1.8× higher with no delivery fee
in play at all.** Per day: 08-17 collection £20.70 (5 orders), 08-18 collection £17.17 (1 order).

📌 **What the number actually is: £23.75 of food per online order across both days (17 orders),
against £11.29 to £14.59 on the till.** Roughly **1.7× to 2×**, and that is real basket size, not fees.

⚠️ **The comparison is channel-vs-channel, not like-for-like, and must be presented that way.** The
till is walk-in/in-house; the website is 11 delivery : 6 collection. A household ordering in is not
the same buyer as one person at the counter. Two days and 17 orders is **directional, not
conclusive** — do not present it as settled.

🟡 **Unverified and honestly labelled:** whether EposNow "Sales" is gross or net of VAT, and whether
it nets off its own charges. Both till figures were **read off screenshots**, not from his data.
**This is a concrete business case for the OI-87 read-only pull.** One set of numbers, no
screenshots, no VAT ambiguity.

### 🔴 The real defect Imran found, which his AOV theory buried: the delivery minimum is FLAT while the fee is BANDED.

`storefront/src/data/menu.ts:604`, `deliveryMinimum: 500` (£5.00, confirmed by Imran 07-27).
Fee bands at `menu.ts:595-601` run **£3.00 (Rhu/Rosneath £4.50, Caravan Park £6.00, Kilcreggan
£7.00) up to Helensburgh £10.00 and Arrochar £15.00.**

His example, `260817-D002`: **£8.48 of food, £10.00 delivery to Helensburgh.** It cleared the £5
minimum and still cost more to deliver than it sold. It is **the smallest food basket in the whole
17-order set** (one order, not the pattern), but the structure that allowed it is live for every
Helensburgh and Arrochar order.

📌 **Proposal, not built, needs Imran's decision: make the minimum scale with the band** (e.g. ≥2×
the delivery fee, so Helensburgh needs £20 and Arrochar £30), or set explicit per-area minimums.
**Registered as OI-88.** Nothing changed in code.

## ✅ 2026-08-17 22:32 UK. THE SCHEDULED DEPLOY OF `4b11c43` FIRED AND LANDED. Superseded the section below; kept for the audit trail.

**Verified on this refresh from effect, not from the job's exit code:** `git ls-remote origin main`
= `4b11c43`; server `~/pos-system` HEAD = `4b11c43`; nginx/frontend/backend container `StartedAt` =
`2026-08-17T21:32-21:33Z` (= 22:32 UK), all five commits pushed as predicted. All 8 containers
(5 POS + 3 Orbit) healthy at the time of this refresh.

🟢 **Consequence: OI-86 (email typo repair, `565b42e`) is now DEPLOYED, not merely committed.**
Wherever this file or `_state/open-items.md` still says "built, not deployed", that is stale.
⚠️ **Its effect in production is still UNVERIFIED** — no typo'd address is known to have come
through since. Deployed ≠ proven working.

## 🕐 2026-08-17. TONIGHT'S SCHEDULED DEPLOY OF `4b11c43` IS ARMED, and there are TWO jobs running, not one. ✅ SUPERSEDED, IT FIRED, see above.

**Verified from the process table at 22:45 PK, not from the checkpoint's narration:**
- **PID 23252**: `deploy_after_close.sh 4b11c43 "2026-08-17 21:30:00"`, started 22:39 PK. **This is
  the real one.** Fires 21:30 UTC = 22:30 UK = 02:30 PK.
- ⚠️ **PID 9812**: `deploy_after_close.sh ad5e8ef "2026-08-17 21:30:00"`, started 22:02 PK. **A
  stale duplicate from an earlier scheduling that was never killed.** It wakes at the same second.

**Why the duplicate is harmless, read out of the script rather than assumed:** the `HEAD ==
$EXPECTED_COMMIT` guard is at `scripts/deploy_after_close.sh:49`, which is **before** the ssh check,
before `pg_dump` and before `git push`. HEAD is `4b11c43`, so PID 9812 dies at line 50 with
*"HEAD is 4b11c43, expected ad5e8ef"* having touched nothing. **It will still print ABORTED, so do
not read that output and conclude the deploy failed.** Judge the deploy by PID 23252's output and
by effect on the server.

🔴 **Do not commit anything before 22:30 UK tonight.** Any commit moves HEAD off `4b11c43` and the
real job aborts too. To commit sooner, kill PID 23252 first and reschedule with
`bash scripts/deploy_after_close.sh <new-sha> "2026-08-17 21:30:00"`.

## 🟡 2026-08-17. OI-87 RESEARCHED, NOT BUILT, NOT SCOPED. The API exists and Imran can switch it on himself. Two things could still kill it, and neither is the transport.

**Findings, with every claim carrying its source URL and the date checked:**
`_context/clients/chick-shack-uk/eposnow-integration-research_2026-08-17.md`.

- ✅ **The API is real and self-service.** Back Office > Web Integrations > REST API > Add Device,
  HTTP Basic auth (Base64 of key:secret), `POST https://api.eposnowhq.com/api/V2/CompleteTransaction`
  (**V2 is deprecated, use the V4 equivalent**). The transaction model carries a **TenderType** and a
  **Tender amount**, which is what "push it in already paid" needs. **No EposNow permission required**,
  which matters given the conflict of interest below.
- ✅ **The mapping fear was largely obsolete, and that is measured not assumed.** OI-45 mirrored his
  till on 07-29, so `storefront/src/data/menu.ts` already carries **25 separate Meal items** and the
  **same four modifier group names** as his EposNow. It is a ~87-row lookup table, not a redesign.
  It still rots on menu edits, so any build must **fail loudly on an unmapped item**, never push a
  partial order (the OI-61 family rule, applied before the bug exists).
- 🔴 **Killer 1: "An API device ... uses one of your device licenses."** This may cost Imran money
  every month and **no price is published on either the UK or US API app page.**
- 🔴 **Killer 2: nobody has proved a pushed transaction lands in his End Of Day.** That is the entire
  business requirement, and **an order that looks pushed but does not reconcile is worse than the
  double entry it replaced.** There is also **no sandbox**, so the first real test runs against his
  live account, after close, with his permission.
- ⚠️ **EposNow sells its own online ordering at "2.00% + 10p per delivery"**, roughly £0.60 an order
  against our £35/month flat. **Their account manager is not a neutral party.** Chase the Sam lead
  for speed; do not let the plan depend on their goodwill.
- 📌 **Not confirmed and honestly labelled: the exact `CompleteTransaction` payload fields.** The
  docs portal renders body params in JavaScript and the Chrome extension has been down since ~08-11,
  so the field list could not be read. "Can it be pushed already paid" is **strongly indicated, not
  proven.**

**Approach set by Malik 2026-08-17: diagnostic, not build.** It is Imran's system, so we find out
what is possible, then propose. **Four stages in section F of the research doc**, and the governing
principle is: **do not design the payload from the docs, read one of his real transactions back
through the API and copy its shape.** Stages 1 and 2 are read-only and risk nothing; stage 3 is a
single test order after close; stage 4 deletes it (`DELETE /api/V2/Transaction/{Id}` exists, so it
is reversible, though **a delete may still show in his "Void Lines" audit report and may not clear
End Of Day**, so tell him first).

🟢 **Read-only access is the sleeper win here.** Pulling his till sales into our reporting would give
Imran **one set of numbers for the whole business** instead of two, and it carries none of the risk
of writing transactions. Not proposed, not scoped, judged after stage 2.

### 🟢 2026-08-17 21:23-21:36 UK. ANSWERED FROM IMRAN'S OWN ACCOUNT, via screenshots he sent. Not from documentation.

Screenshots archived in `_context/clients/chick-shack-uk/refs/eposnow-backoffice/`.

- ✅ **The API is available on his account**, needs no EposNow approval, and is **not currently
  installed** (the AppStore button reads **Get**).
- 💷 **It costs £15 per month** as an AppStore subscription. ⚠️ **Read off a blurred phone photo;
  confirm on the Buy screen before quoting it.**
- 🟢 **Rate limit is 5,000 requests per 24 hours per licence**, quoted from the listing. **That is
  enormous headroom here and is not a risk.** Closes the last of section A's open questions.
- 🔴 **The developer docs' menu path does not exist in his UI.** There is no "Web Integrations"
  anywhere: not in the app grid, not in Setup. **The API section appears only after the app is
  installed.** Documentation and live product disagree, and only the live product counts.
- 🟢 **"Additional Logins" exists under Setup > Company**, which is the clean route to give Malik his
  own Back Office login instead of asking Imran to click through things.
- 📌 **Zapier Integration is also on his AppStore** (subscription), as a no-bespoke-code fallback.
- ⚠️ **Unsettled: whether the £15 licence IS the device licence or consumes another on top.**

**The business case, assumptions stated and unverified with Imran:** ~270 online orders a month at
~90 seconds to re-key, at £11 to £12 an hour, is **£75 to £80 of staff time a month against a £15
tool**. It pays even if the assumptions are generous by half, and that ignores mis-key errors.

🔴 **The open decision is commercial, not technical: who pays the £15.** Imran, us, or a revised
monthly. **Nothing to be bought until Malik decides.**

📌 **Malik's read, and the evidence supports it: the £15 is ADDITIONAL to his current bill.** In the
AppStore list every button said "Get" and the label beneath separated **"Free"** (Apicbase, Epos Now
Capital, Rapid Edit, Factor4) from **"Subscription"** (API, Zapier, Flow, Morph), and the detail page
says **"Buy App"** with a per-month price. Three signals agreeing. ⚠️ **Still inference from UI
labels, not confirmed against his bill.**

🔴 **Nobody should tap "Buy App" to investigate.** No confirmation step has been seen and it is a
live client's billing. **The safe read-only check is Setup > Company > Subscriptions**, which shows
what he pays today and how many device licences he holds, settling both the "is it additional"
question and whether an API device consumes an existing licence.

### ⏸️ 2026-08-17 late. BALL IS WITH IMRAN. He is discussing it with Sam, then deciding.

✅ **The "Sam" lead is no longer just Malik's recollection.** Imran is taking this to Sam himself, so
**a named EposNow contact for this account is real.** The brief's instruction to verify rather than
assume it is now satisfied by Imran's own action, not by a record.

**Nothing is bought, nothing is installed, nothing is built, and nothing has been promised to
Imran.** The research answered what it set out to answer and the next move is his.

**When he comes back, the order of work is unchanged:** confirm the £15 and the licence question,
then install, then section F stage 1 (read-only pull of his catalogue, tender types and a handful of
real transactions) before anything is written to his system.

<details><summary>The original OI-87 framing, before the research</summary>

## 🔵 2026-08-17. OI-87 OPENED. Every online order is re-keyed into EposNow by hand. RESEARCH NOT STARTED.

Imran runs **EposNow** for in-house, dine-in and phone; we supply the online channel only. The two do
not talk, so his team types every one of our orders into EposNow purely to mark it paid and balance
the day. Double entry, during service, and it gets **worse as the channel grows**, which defeats the
point of the channel.

Three constraints, all from the brief at
`_context/clients/chick-shack-uk/eposnow-integration-brief.md`:
1. 🔴 **NOT an EposNow displacement.** Settled on the 2026-07-26 call. We push into his system.
2. 📌 **The "Sam" lead is UNVERIFIED**, being Malik's recollection of an EposNow account manager who did
   technical plumbing for Imran's `C001`/`D001` receipt numbering. If real, it is a warm technical
   contact inside the vendor. Confirm with Imran before relying on it.
3. ⚠️ **The hard part is catalogue mapping, not transport.** Meals are separate products in EposNow
   but modifier groups in our storefront, and any id mapping rots when either side edits a menu.
   **Prove the API exists on Imran's actual plan before designing anything.** QuickBooks Desktop was
   scoped at six weeks, built to 33%, and parked.

**Research only. Nothing built, nothing promised, nothing sent to Imran without Malik approving it.**

</details>

## 🟢 2026-08-17. OI-86 BUILT, TESTED, COMMITTED (`565b42e`). NOT DEPLOYED. Server-side repair, not a checkout prompt.

**The design moved after the register entry was written, and the register was not updated** (fixed on
this refresh). It is **not** the storefront "did you mean?" prompt originally proposed: it is a
**server-side normalisation at send time**, `backend/app/services/email_normalise.py`, so there is
one pipeline and zero friction at checkout. Malik's call.

- **Curated provider tables, never edit distance.** `email.com` is one character from `gmail.com` and
  is a real domain; a distance rule would silently redirect a real customer's mail to Google.
- **Scoped to 14 big consumer providers.** `gmial/gmali/gnail` → `gmail`, `gmail.co/.con/.cim` →
  `gmail.com`; a custom or business domain is never in scope, so `mybusiness.co` cannot be touched.
- 🔴 **The customer's original address is preserved verbatim, always.** Non-negotiable, stated
  explicitly by Malik. Corrected only at send time, never written back.
- **41 unit tests + 2 integration, mutation-checked.** Full suite **608 passed**, same 10 failures +
  2 errors as before.

**Ships with tonight's push.** Backend-only, so `git push` is the right pipeline for it.

## 🔴 2026-08-17. THE WIN-BACK CAMPAIGN PRODUCED ZERO SECOND ORDERS. 84 sent, 83 delivered, ~10% open, 1 click.

Zero spam complaints and zero unsubscribes, so nothing was damaged, but nothing was earned either.
**Two campaigns have now converted at zero** (this and the Google review email, OI-85, at ~240 sends).
📌 **Before a third: 18:35 is the dinner peak, not a good send time.** 15:30 UK, before opening, is
the next thing to try. Nothing authorised.

## 🟢 2026-08-16 22:30 UK. OI-84 DEPLOYED AND VERIFIED LIVE (`baa63f3`, alembic `v8w9x0y1z2a3`). The scheduled unattended deploy ran exactly as written.

**Ran at 21:30 UTC / 02:30 PK / 22:30 UK, thirty minutes after close, via `scripts/deploy_oi84.sh`.**
Preconditions passed (HEAD `baa63f3`, branch main, server reachable, UK hour 22 so shop shut).
**`pg_dump` taken and verified restorable BEFORE the migration**: 42 COPY blocks = 42 live tables,
gzip integrity OK, completion marker present, at
`/root/backups/pos_system_20260816T213005Z_pre_OI84.sql.gz`.

**Verified by effect, in this order:**
- Server `git log` = **`baa63f3`**; alembic **`v8w9x0y1z2a3 (head)`**.
- **Backfill exactly as designed: 45 rows `false`/no-session, 114 rows `true`/session, and ZERO
  contradictory rows across ALL tenants** (no row is card-intent-false while holding a session).
- **The predicate read out of the RUNNING container**, compiled to SQL:
  `intends_card_payment IS false AND stripe_checkout_session_id IS NULL OR payment_authorized_at IS
  NOT NULL OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL`. The new first arm is live.
- **138 chick-shack orders, 133 real, 5 hidden — and all 5 are the right ones**: `260816-D004`
  (tonight's abandoned), `260814-D002`, `260810-D006`, `260810-D001` (the declined card),
  `260807-D005` (the abandoned checkout). Every one `intends_card=True, session=yes,
  authorised=NO`. **No previously-visible order changed state**, which is what the backfill existed
  to guarantee.
- 0 backend exceptions, 0 nginx 5xx, all public URLs 200, CORS correct on the real origin,
  **Orbit CRM untouched** (2-3 months uptime).

⚠️ **A ~2 minute 502 window follows every deploy, and it is the BACKEND STARTUP WINDOW, not the
nginx stale-IP trap.** This was mis-attributed at first and then settled by evidence.

On the OI-84 deploy the 502 appeared while nginx happened to be recreated too, so it looked like the
documented "nginx caches upstream IPs" problem. **The docs deploy an hour later disproved that:
nginx was NOT recreated (still "Up 56 minutes"), the 502 appeared anyway, and it cleared by itself
the moment the backend went `health: starting` → `healthy`.** Confirmed directly: backend at
`172.18.0.5`, and `wget` from inside the nginx container to `http://backend:8000/api/v1/health`
returns healthy JSON.

**So: do not recreate nginx after a deploy on the strength of a 502. Wait ~90s for the backend health
check first.** The stale-IP trap is real but it is a different failure, and reaching for it here
would be treating a symptom that resolves on its own.

📌 **The verification lesson stands and is separate:** the script's URL check ran ~30s after the
containers came up, i.e. too early, and reported a false failure. A deploy check that stops at the
first URL probe can cry wolf; one that never probes at all misses a real outage. **It should poll
until healthy or a timeout, not sample once.**

📌 **What this does NOT prove.** No stored row is currently inside the 0.3s window, so production
data cannot demonstrate the window is closed. **The tests are what prove that**, and they are
mutation-checked. The live check proves the predicate shipped, the backfill is correct and nothing
regressed.

<details><summary>Build detail, before deploy</summary>

## 🟡 2026-08-16. OI-84 BUILT, TESTED, MUTATION-CHECKED. NOT YET DEPLOYED, waiting for the 22:00 UK close. Malik: "for prepaid orders, we show in POS only after stripe has authorized. any abandoned carts, refused payments dont show. cash on delivery/collection gets shown as it is."

**The fix, in five parts:**
1. **New column `orders.intends_card_payment`**, written in the order's own INSERT
   (`public_order_service.py`, from `data.payment_method == "card"`). Migration
   `v8w9x0y1z2a3`, backfilled `= (stripe_checkout_session_id IS NOT NULL)` so **no historical order
   changes meaning**.
2. **`is_real_order()`'s cash arm** now requires **both** no card intent **and** no Stripe session.
   Belt and braces on purpose: the flag only ever *adds* information, so a pre-migration row or a
   future path that forgets the flag still cannot be mistaken for cash while it carries a session.
3. **New `order_visibility.is_card_order(order)`**, the row-level twin, because the same question
   was being asked inline in **four** files (tablet order card, confirmation email payment line,
   printed ticket, `accept_order`'s money guard) — all four reading the session id, all four wrong
   during the window. **That is this module's own lesson applied to itself.**
4. **`accept_order` keys on the intent**, and refuses outright when a card order has no session
   (the customer never reached Stripe, so there is nothing to confirm and nothing to capture).
5. Email, printed ticket and the tablet's `is_card_order` flag all routed through the helper.

**Verified, not assumed:**
- **New file `tests/test_card_intent_window.py`, 6 tests**, plus **2 end-to-end tests** through the
  real endpoint in `test_public_tenant_routing.py`. Both sides asserted (card *and* cash), and the
  untouched arms too, because a test that only exercises the line you edited proves nothing.
- **Mutation-checked twice.** Reverting the predicate to `stripe_checkout_session_id IS NULL` fails
  `test_a_card_order_without_a_stripe_session_is_not_real`; setting `intends_card_payment=False` in
  the service fails `test_a_card_order_records_the_intent_at_creation_and_stays_hidden`. **Neither
  test can pass against the bug.**
- **Full suite 565 passed, 10 failed, 2 errors — identical failures to before the change** (8 parked
  QB-Desktop, plus `test_void_with_reason_succeeds` (401, auth) and
  `test_transition_blocked_without_payment` (stale assertion on reworded copy); both inspected, both
  unrelated). **+9 tests, zero new failures.**
- Migration applied locally: backfill gives `f/f 29` and `t/t 2`, **no row in a contradictory state**.
- `ruff` clean on all 9 touched files.

✅ **COMMITTED as `baa63f3`, NOT pushed.** Ten files staged by explicit filename; the ~132-file dirty
tree and OI-60's untested work left exactly as they were. Staged diff scanned for secret-shaped
strings: **0**.

🕐 **DEPLOY SCHEDULED for 21:30 UTC = 02:30 PK = 22:30 UK**, thirty minutes after close, on Malik's
instruction (2026-08-16). Runs unattended via `scripts/deploy_oi84.sh`, which refuses rather than
guesses:
- aborts unless HEAD is still `baa63f3` and the branch is `main`;
- **aborts if the UK hour is 15-21**, i.e. if the shop is open;
- **`pg_dump` FIRST and verified restorable before the migration runs** (gzip integrity, completion
  marker, and a COPY-block count floor), because this deploy carries an `ALTER TABLE` plus a
  backfill `UPDATE`;
- polls the server until it reports `baa63f3` rather than trusting the push;
- verifies by effect: alembic version, the column and its backfill counts, the fix greppedout of the
  **running container**, `docker ps` with Orbit CRM's uptime, public URLs, CORS on the real origin,
  and backend exceptions since deploy.

⚠️ **Two real traps found while building that script, both worth keeping.**
1. The first draft hardcoded `TARGET_EPOCH=1755379800`, which is **2025**, not 2026. It would have
   made the "wait until 22:30" branch fall straight through and deploy immediately, mid-service.
   The target is now derived from a date string. **Never hand-compute an epoch.**
2. **`TZ=Europe/London date` silently returns local time on Git Bash for Windows**, with no error.
   The shop-open guard was written that way and was reading the wrong clock while looking correct.
   It now reads the UK hour **off the droplet**, which has real tzdata and handles BST.

**The guard was tested live, not assumed:** running `--now` at 20:30 UK aborted with *"it is 20:xx UK
and the shop is open"*, exit 1, before any dump or push.

**Fallback if the scheduled run dies with the session:** `bash scripts/deploy_oi84.sh --now` after
close does the same thing immediately, with the same refusals.

</details>

<details><summary>The diagnosis, before it was built</summary>

## 🔴 2026-08-16. OI-84 NEW, DIAGNOSED NOT BUILT. Malik saw an order chime, appear, vanish for ~30s, then come back. He was right, and the window it exposes can accept an unpaid card order as if it were cash.

**His hypothesis, verbatim: "that order still populates briefly in POS as it is placed, but then the
payment guardrail comes into play." Confirmed, with one correction: the guardrail is not late, its
INPUT is.**

**The mechanism, every step read out of the code:**
1. The storefront places a card order in **two API calls**: `POST /{slug}/orders` creates and
   **commits** the row (`public.py:154`), then `POST /{slug}/orders/{id}/checkout-session`
   (`public.py:209`) sets `stripe_checkout_session_id`.
2. Between those two calls the row has **no session id**, and `is_real_order()`'s first arm is
   `stripe_checkout_session_id IS NULL` — the cash-on-delivery arm. **So a card order is
   indistinguishable from a cash order for that instant** and the tablet correctly shows it.
3. The tablet polls every **10s** (`OnlineOrdersPage.tsx:50`) and chimes on newly-seen orders, so a
   poll landing inside the window produces exactly what Malik saw: sound, order, then it disappears.
4. It stays hidden until Stripe authorises, **measured today at 26s (D003), 32s (D001), 39s (D005)**.
   Malik's "10-20 seconds" was the right order of magnitude, eyeballed.

**Window size, measured from two abandoned orders whose rows were never touched again: 0.32s
(`260816-D004`) and 0.26s (`260807-D005`).** Against a 10s poll that is roughly a **3% chance per
card order**, i.e. a handful of times across the shop's 126 orders. Matches "a couple of times"
exactly. **Not measured: how often it has actually fired.**

🔴 **The part that is worse than a cosmetic flicker.** `accept_order` guards the money with
`if order.stripe_checkout_session_id and order.payment_captured_at is None:`
(`public_order_service.py:806`). **During the window that id is NULL, so the entire card
verification block is skipped** and the order is accepted as though it were cash on delivery.
`accepted_at` is then set, which is its own arm of `is_real_order()`, so it stays visible **forever**
and never gets captured. Staff have up to 10s to tap Accept.
**Low probability, real consequence: food cooked, no money held, and a card customer who was never
charged.** Nobody has reported this happening; it is a path, not an incident.

⚠️ **Same family as OI-61/65/66/68/73, with a twist worth keeping.** The rule has one home and that
home is correct. What is wrong is that **the predicate reads a field that does not exist yet**.
A single definition is necessary and not sufficient: its inputs have to be populated before anything
queries it.

**The fix, not built and not authorised.** `payment_method` **is not a column on `orders`** (checked:
`column "payment_method" does not exist`); the intent lives only in the request body, which is why
`create_public_order` can correctly skip the confirmation email for card orders while the predicate
cannot see the same fact. So: persist the intent at creation, add one arm to `is_real_order()`, and
backfill existing rows as `intends_card = (stripe_checkout_session_id IS NOT NULL)` so history is
unchanged. Also fix the `accept_order` guard to key on the intent rather than the session id.
Migration plus predicate plus tests; a deploy, backend only.

</details>

## 🟢 2026-08-16. `260816-D004` was skipped for the third time in ten days, and the gate was right again. Abandoned card checkout, customer immediately re-ordered.

`260816-D004`, **Damien Callaghan**, delivery, **£30.97**, created **18:31:54 UK**, `unpaid`, no
`payment_authorized_at`, and `updated_at` is **0.32s** after `created_at`, so nothing has touched the
row since the checkout session was made. He reached Stripe and never completed it.

**He re-ordered seven minutes later and paid.** `260816-D005`, same name, same phone,
**£46.94** (a *bigger* basket, not a cheaper one), authorised 18:39:39, accepted 18:40:16, in the
kitchen. **The shop lost nothing.**

⚠️ **Third occurrence in ten days** (`260807-D005` abandoned, `260810-D001` declined, now this),
each with a different cause and the gate correct every time. **The unbuilt idea from 08-07 now has
three data points: surface an abandoned/declined count on the reports page so a number gap has a
visible reason.** Still not built and still not asked for.

## 🔴 2026-08-16. THE REVIEW EMAIL HAS PRODUCED ZERO REVIEWS IN SIX DAYS. Settled by the review dates, not inferred.

**Profile: 16 reviews, 5.0 average, every one five stars. The newest is ~3 weeks old (~26 July).**
The review email went live **10 Aug**. **Every one of the 16 predates it**, clustered around the
shop's opening. So roughly **240 sends have produced 0 reviews**, and none of the usual excuses
apply: the button works (verified tonight, opens the correct Chick Shack profile with the star form
ready), the email lands in **Primary** not Promotions, and the open rate is ~55%.

⚠️ **I was wrong here and Malik was right.** He said "0 reviews"; I pushed back citing the 16 total
and called it an attribution gap. The dates killed that. **A total is not a rate.** Check when,
not just how many, before contradicting him.

📌 **Baseline now recorded so this is measurable from here: 16 reviews / 5.0 on 2026-08-16.** The
review email shipped 10 Aug to move this number and nobody wrote the number down that day. A feature
shipped to move a metric needs the metric recorded on the day it ships.

⚠️ **Clicks understate and should not be the metric** (Google links often open in the Maps app
without registering a click) but at 0 reviews that no longer rescues anything. **Count reviews.**

**Not diagnosed and not built:** why it converts at zero. Candidates are the 3-hour delay landing
after people have moved on, the ask being work rather than a tap, and the email arriving from
`orders@` rather than a person. Nothing here is authorised.

**Verified tonight, so these are not the open questions:** the review email's button works, opens the
correct Chick Shack profile (Main Street, Garelochhead G84 0AN) with the star form ready to post; the
email lands in **Primary**, not Promotions; open rate is ~55%.

⚠️ **Clicks are not the metric and will understate.** Google review links frequently open in the Maps
app without ever registering a click, which is consistent with 0-2 recorded clicks a day against a
profile that has 16 reviews. **Count reviews, not clicks.**

**Lesson, generalises beyond this feature:** a feature shipped to move a metric needs that metric
recorded on the day it ships. See [[dont-over-verify-what-malik-knows]] for the opposite failure; this
is the under-measurement one.

## 🟢 2026-08-16 ~18:35-18:46 UK. OI-83 FIRED AND VERIFIED. 84 win-back emails sent to every customer who had ordered exactly once. Subject: "Fancy the same again, {first_name}?"

**Verified by effect, not by exit code.** Script reported 84 submitted, 0 failures. Brevo's own
daily report for 16 Aug then read **102 requests, 101 delivered, 0 hard bounces, 0 soft bounces,
0 spam reports, 0 unsubscribes, 1 blocked**.

⚠️ **"Sent" in the script means the Brevo API accepted the call, not that it was delivered.** The
one block proves the distinction matters. Judge a campaign by the provider's delivered count, not
by the sender's loop counter.

**The single block was pre-existing and not caused by this send:** `dave_cameron@hotmail.com`,
`contactFlaggedAsSpam`, blocked **2026-08-04**, twelve days ago. That customer marked a Chick Shack
email as spam back on 4 Aug, which predates the review email entirely, so it was an order
confirmation. Brevo auto-suppressed them and correctly refused this one. **So 83 of 84 landed.**

✅ **The bad-domain guard paid off, measurably.** Zero hard bounces. Had `gmail.con` and `gmail.cim`
not been excluded, the run would have posted 2 hard bounces against a domain whose record was
previously spotless.

**Cohort moved between staging and firing: 83 at the dry run, 84 at send** (another first-time
customer landed in the gap). The script recomputes at run time, which is why that was harmless.

📌 **Still true and still worth fixing before the next campaign:** unsubscribe is a `mailto:`
"reply with STOP", not a one-click route. Nothing in the codebase yet.

**Built as a script, not a feature**, so nothing is deployed and the droplet is never recreated
during service: `backend/app/scripts/winback_email.py`, piped into the running backend container at
`/tmp/` and run with `docker exec`. Three modes, only one of which mails customers: `--dry-run`,
`--test EMAIL [--sample ORDER_NUMBER]`, `--send`.

✅ **Test sent and verified delivered, 2026-08-16.** Rendered order `260802-011` (2 items with
modifiers, £22.17, close to the £24.91 AOV) and sent it to Malik. Brevo confirms **12 requests, 12
delivered, 0 bounces, 0 blocked** for the day. **No customer has been emailed.**

**The list, measured not estimated** (same `is_real_order()` predicate as OI-82, so it reconciles):
- **103 people on the list**, all 126 real orders carry an email, none missing.
- **85 ordered exactly once**, 16 twice, 3 three or more. The list grew 94 → 103 → 85-one-timers in
  two days; it moves, so re-run the dry run before firing.
- **83 will actually be mailed.** Send takes ~10.4 min at one every 7.5s (8/min).

🔴 **Two addresses are undeliverable and it is not just a campaign problem.** `gmail.con` and
`gmail.cim`, both one-character typos of gmail.com typed at checkout. They pass an RFC-shaped regex,
which is why the hygiene query reported **zero** malformed. **Those two customers never received
their order confirmations either, and never will.** Excluded via `BAD_DOMAINS` rather than mailed
into a hard bounce; the domain's record is currently spotless (0 hard, 0 soft, 0 spam, 0 blocks over
7 days) and worth keeping that way. Worth telling Imran, separately from this campaign.
⚠️ One of the two is **Imran's own £2.78 test order** from 01 Aug (a Pepsi and a chilli sauce), which
would otherwise have been recipient #1.

⚠️ **Correction to my own earlier advice, recorded so it does not get repeated:** I proposed a
credit floor to stop the campaign exhausting the daily send limit. Malik pushed back and he was
right. Peak transactional day is **50**, campaign is **83**, cap is **300**. It cannot bind. The
guard was over-engineering for a volume this business is nowhere near.

**Verified limits, from the live account and Brevo's docs, not memory:** Free plan, **300/day**,
resets daily, no rollover. API limit 1,000 req/sec, i.e. irrelevant here. Last 7 days of real sends:
26, 47, 42, 47, 36, 50, and 12 today. The 7.5s pace is for **receiving-side reputation**, not the
API: a domain that has only ever sent one-to-one transactional mail suddenly emitting 83
near-identical messages in ten seconds is what Gmail scores as a new bulk sender.

📌 **Unsubscribe is a `mailto:` "reply with STOP", not a one-click link, and that is deliberate for
send #1.** There is still no unsubscribe column, token or route in the codebase. The footer link is
honest and works today, replies land at `orders@chickshackg84.com`, and the script honours a
`/tmp/winback_optout.txt` list. A real one-click route should exist before the list is much bigger.
⚠️ I earlier estimated that build at "about a day"; Malik called it out and he was right, it is well
under an hour. Do not pad estimates.

📌 **`/tmp` in the backend container is a 64M tmpfs and the rootfs is read-only** (`docker cp` is
refused outright, pipe via `docker exec -i sh -c 'cat > …'` instead). The sent-log therefore does not
survive a container restart, so **do not deploy during the ~10 minute send**. The per-recipient
progress is also printed to stdout and captured host-side, which is the real record.

<details><summary>Original OI-83 framing, before the build</summary>

## 🔵 2026-08-16. OI-83 NEW, DISCUSSION ONLY. Malik wants visually engaging "we miss you" emails to past website customers. No discounts, no coupon codes. Nothing built, nothing authorised.

**The data already says this is the right target.** OI-82 measured it two days earlier: **81 of 94
unique customers (86%) ordered exactly once**, a two-time customer is worth **£42.41** lifetime
against **£27.06** for a one-timer, and converting 20 of the 81 is worth roughly **£500**, about
twelve times what the proposed discount would have given away. Repeat rate, not basket size, is
where this business leaks.

**Three facts that constrain the design, all verified in the repo on this refresh:**
1. **We do have the addresses.** Email is a hard requirement at checkout
   (`storefront/src/components/Checkout.tsx:103-111`, `emailOk` gates the submit button), so every
   real online order carries one.
2. 🔴 **There is no unsubscribe mechanism anywhere in the codebase.** `grep -rn -i
   "unsubscribe|marketing_consent|opt.out|opt_in" backend/app` returns **one hit and it is the
   WebSocket room manager.** Order emails are transactional and never needed one. A win-back email
   is direct marketing under UK PECR and legally needs an opt-out in **every** message plus a
   suppression list that is actually honoured. **This is the build, not the artwork.**
   Compounding it: the checkout collects the address under a purely transactional promise ("We'll
   email you when the shop confirms your order"), and offers no opt-out at the point of collection,
   which is one of the soft opt-in conditions.
3. **There is no food photography and there never has been.** Recorded in
   `email_service.py:61-64` ("No logo/mascot asset exists, checked 2026-07-30"). Every template
   therefore has to earn "visually engaging" from typography, colour and layout, and the highest
   value thing to ask Imran for is **8 to 10 phone photos of the real food**.

**What exists and can be reused:** Brevo API send rail (`_send_via_brevo`), the branded 600px
`_html_shell` with the Chick Shack wordmark and badge, item/total tables, escaping of all
customer-controlled strings, and the **proven background worker pattern** from the Google review
email (15-minute timer, atomic conditional UPDATE claim so 4 workers cannot double-send, shop-local
send window). A campaign sender is that worker with a different query, not new infrastructure.

⚠️ **Timing objection that outranks the artwork: the shop is 16 days old.** Trading started 31 Jul.
A "we miss you, it has been ages" email to someone who ordered nine days ago at a two-week-old
takeaway reads as desperate and is factually silly. The genuinely lapsed cohort is small and needs
counting before anything is written.

Templates and the discussion are in the artifact; nothing has been sent, built or authorised.

</details>

## 🔵 2026-08-14. OI-82 ANALYSED, NOT BUILT. Imran proposes 10% off orders over £50. The threshold is set above the 93rd percentile of his own baskets.

Measured read-only against production, whole trading history: **31 Jul to 14 Aug, 108 real orders,
£2,690.15 food revenue, AOV £24.91, median £22.95, p90 £38.15.**

- **Only 7 orders (6.5%) already clear £50.** 10% off them = **£42.10 per 15 days (~£85/month)**
  given to customers who spent it anyway. Guaranteed cost, speculative uplift.
- **The nudge pool is empty.** 71% of orders are >£20 short of £50; the 3 orders in £40-50 average
  a **£2.73** gap, so each would get ~£5 off for adding £2.73. Break-even (65% GM assumed) needs
  **S < £42.31** for a nudge to pay at all, and ~9 to 28 extra £50 baskets per fortnight from a
  £30-50 pool of **24 orders total**. Not reachable.
- **A £50-plus basket is a different customer, not an upsell**: 7.86 units/order vs 2.72 below £50.
- **A percentage costs more the bigger the basket.** Capped gives (free can approx **£7** per 15
  days at a £35 threshold, free delivery over £40 = **£41.00**) buy more behaviour per pound.
- **£40 is the best possible line and £50 is the worst on the board.** Nudgeable pool within £8
  below, per free giveaway: £25 → 0.75, £30 → 0.88, £35 → 1.47, **£40 → 1.70**, £45 → 0.40,
  **£50 → 0.43**. Too low and everyone qualifies free; too high and nobody can reach.
- 🟢 **THE OPPORTUNITY IS THE BOTTOM OF THE MENU, NOT THE TOP. 53% of orders are one or two items
  averaging under £20** (27 single-item at £12.39, 32 two-item at £19.70), i.e. **59 orders a
  fortnight against 7 over £50**. Of the 67 orders under £25, **50 have no side, no drink and no
  dip at all**, yet in the £25-38 band only 13 of 32 lack a side, so bigger orderers already
  attach. **+£1 on every order = +£111/fortnight, +£2 = +£222**, against the discount's -£42.
- **The real leak is repeat rate: 81 of 94 unique customers (86%) ordered once.** A two-time
  customer is worth **£42.41** lifetime vs **£27.06**; converting 20 of the 81 is ~**£500**,
  twelve times what the discount gives away.
- **Upselling is already proven here and discounting has never been tried:** paid chips upgrades
  have earned ~£42 on their own, the same as the whole discount scheme would cost.
- ⚠️ **It is a build, not a setting**: `discount_amount=0` is hardcoded
  (`public_order_service.py:572`) and the storefront has no promo UI at all.
- 📌 **Assumption, not fact: 65% food gross margin**, and the free-item costings (~40p a can) too.
  Only Imran has the real numbers, and every break-even figure above moves with them.

**Recommendation, ranked:** checkout add-on prompt (add chips / can / dip) → "make it a meal" on
the 27 one-item orders → repeat voucher on the existing review-email rail → and only if a
threshold is insisted on, **£40 with a free item, never 10% over £50**.

Write-up `_context/clients/chick-shack-uk/discount-analysis_2026-08-14.md` with re-runnable
read-only SQL beside it; register entry `_state/open-items.md` OI-82; plain-English artifact
`5fc8f9a0-9683-41f9-b45a-9d9c845f2a98`. **Nothing built, nothing authorised. Waiting on Imran.**

## 🟢 2026-08-14 ~00:40 PK. OI-81 SHIPPED AND VERIFIED LIVE (`2366c99` + Cloudflare `c8d8a9b6`). Deployed DURING service on Malik's explicit instruction ("deploy because we can have a live runtime experience").

**Imran's two checkout changes, requested 2026-08-13, live the same day:**
1. **"Service Fee" is now "Platform Fee"** on every surface a customer or the shop sees: storefront
   checkout + confirmation, the Stripe payment page line item, the order emails, the printed ticket,
   the tablet queue. Label-only; the `service_fee` column and every field name stay.
2. **Tip at checkout**: None / £2 / £4 / £5 / Other(custom), default none, both service types, no
   explanatory copy (Malik cut the "goes to your rider" line as redundant). New `orders.tip` column
   (migration `u7v8w9x0y1z2`), validated **0..£20 server-side** (fat-finger guard: a "350" for
   "3.50" can never charge), snapshotted at creation, included in `total`, **never taxed, never
   counted toward the delivery minimum**. Card: its own "Tip" line on Stripe, so £25.75 + £3.50
   charges £29.25 in one payment (Imran's own example). Cash: prints as its own Tip line and rides
   the `COLLECT` total for the rider.
3. **Tips reporting** (Malik's addition): `prepaid-vs-cod` now returns `prepaid_tips` / `cod_tips`
   under the **same money-actually-taken rule as revenue** (a tip can never sit in a bucket its
   order's revenue is not in — the OI-61-family rule imported, not re-expressed), CSV rows, and a
   Tips section (Total / Card / Cash) on `/online-orders/reports`.

**Verified live, by effect:** server `git log` = `2366c99`; `orders.tip` column present, alembic at
`u7v8w9x0y1z2 (head)`; "Platform Fee" read out of the running container in print/stripe/email
services, zero stale "Service Fee" strings (the one grep hit is a comment); live menu API 200 GBP;
live bundle `index-CviMWmK5.js` (hash identical to the locally-verified build): "Service Fee" **0**,
"Add a tip" 1, "Maximum tip is" 1, OI-78 connection copy intact; **0 backend exceptions, 0 nginx
5xx** since recreation; **Orbit CRM untouched** (2-3 months uptime).

**Zero regressions, proven not claimed:** full suite **546 passed** vs **536** on a clean-HEAD
`git worktree` run at the same clock, **identical 21 failures + 2 errors line-for-line either side**
(parked QB-Desktop suite + the OI-63 time-of-day set, which always fails in the after-midnight-PK
window this ran in). The +10 are the new tip/rename tests. Both frontends typecheck clean, ruff
clean on all touched files.

🔴 **Found and fixed a real drift: OI-78's storefront source was live on Cloudflare (`f0d8764a`)
but never committed to git.** The 08-13 checkpoint's "Files Modified (committed)" claim was wrong —
`App.tsx` retries, `menu.ts` loading state and the connection-failure copy existed only in the
working tree. Deploying the storefront without them would have silently REGRESSED the live site
back to no-retry behaviour. `2366c99` commits them; git now matches production. Logged in
ERROR_LOG.md.

📌 **Not verified and it cannot be from here: a real order with a real tip.** No test order was
placed (live service, real Stripe, real tablet). **Malik's UAT is the last step:** add any item,
pick a tip, check the total moves, pay by card, and confirm the Stripe page shows the Tip line and
the ticket prints it. The reports tiles read zero until the first tipped order lands.

**Closed today:** OI-77 (site served over plain HTTP, killing CORS), OI-78 (connection-failure copy
and retry), OI-79 (chips not recorded on meals).

## 🟢 2026-08-12. OI-77 ROOT-CAUSED AND FIXED IN 40 MINUTES. The site served over plain HTTP, which killed CORS, which silently killed ordering.

**THE ANSWER, and it was not signal and not caching: `http://chickshackg84.com` served the full app
over plain HTTP and never redirected.** The page origin was then `http://…`, the menu fetch to
`https://eats.sitaratech.info` carried that origin, the API correctly refused it **no ACAO**, the
browser blocked the response, `store/menu.ts:76` set `source: "fallback"`, and checkout printed
*"Online ordering is coming very soon"*. **Deterministic, not intermittent: every visitor arriving
over http was silently unable to order.**

**The clue was in Imran's own screenshot and was nearly missed.** Malik spotted **"Not Secure"** in
Safari's bottom address bar and told me to check it first. That was the whole case. **Lesson: the
browser chrome in a screenshot is evidence, not decoration.** Two earlier hypotheses (stale bundle,
bad rural signal) were both wrong and both plausible.

**Why it looked device-specific and wasted an hour of guessing:** a browser that has ever visited the
https site upgrades automatically forever after, so Malik's phone and laptop could never reproduce it.
**Incognito has no history and no HSTS, so it lands on plain http.** That is the entire difference
between the two devices, and it is why "works on mine" was not evidence of anything.

**Fixed 2026-08-12 by Malik, Cloudflare → SSL/TLS → Edge Certificates → Always Use HTTPS = On.**
Zero code, zero deploy, zone-level. **Verified after the change, not assumed:**
- `http://chickshackg84.com/` and `http://www.chickshackg84.com/` → **301**, **single hop**, no
  redirect loop (the dashboard warns about `ERR_TOO_MANY_REDIRECTS`; there is none).
- Full customer path simulated: bare http domain → lands `https://chickshackg84.com` → menu fetch with
  that origin returns **200 + `access-control-allow-origin: https://chickshackg84.com`** → 87 items,
  GBP, `ordering_paused false` → **`canOrder` = True**. Ordering is live on the exact path that failed.
- App still served on the final URL (`index-D9lZ_Z-R.js`, unchanged, no deploy was needed).

⚠️ **Deliberately NOT fixed by allow-listing `http://` in CORS.** That would have made ordering work
over an unencrypted connection, putting customer name, phone and address in clear text. Forcing HTTPS
is the correct fix and the tempting one was the wrong one.

**Unmeasured and worth knowing: how many orders this cost.** Anyone arriving from a typed bare domain,
an old `http://` link or a directory listing hit this silently. The QR is https so scanners were fine.
Cloudflare Analytics' http-vs-https split would size it. **Not checked yet.**

**Still open from this incident: HSTS** (same Cloudflare page, belt and braces so a browser never tries
http again). Left off deliberately for now because a long `max-age` is awkward to reverse; revisit once
Always Use HTTPS has a few days on it.

<details><summary>Original diagnosis before the "Not Secure" clue, kept for the trail</summary>

## 🟡 2026-08-12. Imran: "there's an issue on the website." NOT AN OUTAGE. His device could not reach the API. Registered as OI-77.

Imran sent a photo of a phone at checkout showing **"Online ordering is coming very soon / We're not
taking online payments just yet. Give us a ring…"** with a **£23.18** basket (subtotal £22.48 +
£0.70 service fee) and the two Call buttons. He says he was in an **incognito** session. Malik placed
a real test order minutes later that worked: `260812-C001`, collection, **PAID CASH**, accepted 17:01.

**That screen has exactly one cause in the currently deployed bundle, and it is not a shop setting.**
`Checkout.tsx:402` branches on `orderingLive = canOrder(menuSource, orderingPaused)`, and
`store/menu.ts:93` defines it as `SHOP.orderingEnabled && source === "api" && !paused`. The copy
shown is the **non-paused** branch, so `orderingPaused` was false. `SHOP.orderingEnabled` is `true`
and has been since `90190a2` (2026-07-29). **Therefore `source !== "api"`: the `GET
/public/chick-shack/menu` call failed on that handset**, the hardcoded fallback menu in
`data/menu.ts` rendered instead, and ordering was correctly switched off because fallback ids are
slugs the order endpoint rejects with a 422.

**Everything on our side was verified healthy at the time of the report, not assumed:**
- Live API `GET /api/v1/public/chick-shack/menu`: **200, GBP, 8 categories, 87 items,
  `ordering_paused: false`, `ordering_paused_message: null`.** Identical to the 08-09 reading.
- **8 consecutive requests: 8× 200, 0.93s to 1.06s, TTFB ~0.70s, no variance.** So an intermittent
  backend timeout past the client's 12s `AbortController` cutoff (`lib/api.ts:196`) is ruled out.
- **CORS correct on both real origins**: `https://www.chickshackg84.com` and
  `https://chickshackg84.com` each get their own `access-control-allow-origin`;
  `chickshackg84.pages.dev` and `null` correctly get none.
- **Deployed bundle resolved properly** (`index.html` → `/assets/index-D9lZ_Z-R.js`, 200, 196,950
  bytes), same chunk hash as 08-09. It calls `https://eats.sitaratech.info/api/v1` and contains
  `Service Fee` and the `coming very soon` string.
- 11 Aug ran clean to `260811-C013`, all card, all paid.

**Malik asked whether it was a stale cached bundle on their phone. No, and this is settled two ways.**
The handset rendered the **Service Fee** row, which only exists from `f06979f` (2026-08-03), so the
bundle is from 03 Aug or later, and in every bundle since 29 July `orderingEnabled` is `true`. And he
was in **incognito**, which loads fresh anyway. ⚠️ There *was* a one-day window (`c68e616` 07-28 →
`90190a2` 07-29) when `orderingEnabled` was `false` and this screen showed unconditionally, but no
such bundle can also carry the service fee.

**So the fault is between his handset and `eats.sitaratech.info`.** Unconfirmed and only he can
settle it. 📌 **Incidental observation, treat as unverified:** the status bar in the photo appears to
be Arabic script (reads like **اتصالات / Etisalat**, a UAE carrier), which would mean the handset is
not a UK device on a UK network. Worth confirming whose phone it is before assuming UK customers are
affected.

**The 10-second test that settles it, on his device:** open
`https://eats.sitaratech.info/api/v1/public/chick-shack/menu` directly in the same browser. **JSON
means the network is fine and the problem is browser-side** (content blocker, private-mode
restriction, extension). **A spinner or an error means his network or DNS cannot reach that host**,
which is the whole answer.

### ⚠️ Three real product defects this exposed, none of them the reported "outage". Do not build without Malik's say-so.
1. **The message is wrong and actively damaging.** A shop that has been taking real orders for two
   weeks tells a customer "Online ordering is coming very soon". That reads as "this place has not
   launched yet", which is why Imran read it as the site being broken. It should say we cannot reach
   our system right now, offer **Retry**, and keep the phone numbers.
2. **One failed fetch kills the whole session.** `App.tsx:77` loads the menu **once on mount** with
   **no retry**. After a single blip the customer browses a full menu, builds a basket, and is only
   told at the **checkout total** that they cannot order. Nothing recovers it but a manual reload.
3. **The storefront depends on a cross-origin call to an unrelated-looking domain.** The page is
   `chickshackg84.com`; the API is `eats.sitaratech.info`. Any tracker blocker, DNS filter, carrier
   filter or strict private-mode setting can drop that request, and it fails **silently** into the
   copy above. Routing the API through the shop's own domain (a Cloudflare route at
   `chickshackg84.com/api/*`) would remove the cross-origin call, the CORS surface and the blocker
   surface in one move. **This is the structural fix; 1 and 2 are the cheap ones.**

**Any fix here is a storefront change, so it ships via `cd storefront && npm run deploy` to
Cloudflare, NOT `git push`.** See [[chick-shack-two-deploy-pipelines]].

**Next action: Malik sends Imran the one-URL test above. Nothing is built and nothing is authorised.**

*Superseded within the hour: the cause was the http origin, above. The reachability test was never
needed. The three product defects listed in this block all still stand and are still unbuilt.*

</details>

## 🟢 2026-08-13 02:30 PK. OI-79 + OI-78 SHIPPED AND VERIFIED LIVE (`429ce34` + Cloudflare `f0d8764a`). Deployed unattended, after the 22:00 close, on Malik's instruction.

**Measured the problem before fixing it. It was worth fixing: 23 of 112 meal lines since launch,
20.5%, roughly one meal in five and about two a night, reached the kitchen with no chips choice at
all.** Read-only count against production, using the *denormalised* names on `order_items` /
`order_item_modifiers` so the 08-12 group rename cannot re-interpret history. Steady across the whole
period, no trend: 4, 1, 3, 2, 0, 6, 1, 1, 2, 1, 2 per day from 02 to 12 Aug.

**Shipped, in this order, all after the shop closed and with nothing in flight** (last real order
~2h earlier; `260812-D005` showing `in_kitchen` is a stale status from 18:xx with six later orders
all `completed`):
1. **`pg_dump` first, and verified restorable rather than assumed** — 207K gzip, `gzip -t` OK,
   completion marker present, **42 COPY blocks = 42 live tables**, **120 orders in the dump = 120
   live**. `/root/backups/pos_system_20260812T210746Z_pre_OI79.sql.gz`.
2. **Chips group → `required: true`, `min_selections: 1`**, and `display_order` Peri-Peri Heat `1`,
   Chips `2`, both drink groups `3`, Add a dip `4`. Single transaction, **every statement scoped to
   the chick-shack `tenant_id`** — `uq_modgroup_tenant_name` is (tenant, name), so an unscoped UPDATE
   would have reordered Cosa Nostra's and demo-restaurant's menus too. Blast-radius query confirmed
   **0 rows** touched on any other tenant. All 6 options and prices unchanged, Regular Chips still 0.
3. **Backend `429ce34`** — the `display_order` sort, pushed with **2 files staged by explicit
   filename**, 0 secret-shaped strings in the staged diff, the ~127-file dirty tree and OI-60's
   untested work left exactly as they were.
4. **Storefront OI-78** via `npm run deploy` to Cloudflare, version `f0d8764a`.

**Verified live, by effect and not by exit code:**
- Server `git log` = `429ce34`; backend/frontend/nginx recreated (~1 min); **Orbit CRM untouched**
  (`orbit_api` 2 months, `orbit_db` / `orbit_web` 3 months uptime).
- The sort read **out of the running container**: present at line 136, old unsorted line count **0**.
- **The public menu now serves `1. Peri-Peri Heat  2. Chips  3. Adults Meal Deal Drink  4. Add a dip`**,
  exactly what Imran asked for. **Chips `required=True, min=1` on all 25 meals**, and **0 meals** have
  Chips ordered after the drink. Menu healthy: 87 items, 8 categories, GBP, not paused.
- Live storefront chunk resolved `index.html` → `/assets/index-D5HykxJm.js`: new copy present,
  `coming very soon` **0**, `not taking online payments just yet` **0**, `ordering is off right now` **0**.
- **0 nginx 5xx, 0 backend exceptions.** The three 400s are the deploy runner's own empty request
  lines, as on 08-08. All six public URLs 200, including `http://` → 301 → `https://`.

⚠️ **Malik caught a real copy error before it shipped.** The first draft of the OI-78 warning read
*"ordering is off right now"*. **Ordering was not off** — the shop was open and taking orders; it is
the customer's connection that failed. Shipped wording is now *"Your internet connection has
dropped"* / *"We're open and taking orders as normal. Your phone just can't reach us right now."*
**A status message must name whose fault it is, and getting that backwards tells the customer the
shop is shut.**

⚠️ **CI and Deploy-to-Staging are RED and have been on every one of the last 8 commits**, including
ones that shipped fine (`c03e612`, `abf6177`, `1033943`, `52b1d1f`, `a49fef9`, `2795ca2`, `5dda69f`).
Only **Deploy to Production** is green and meaningful. **A pipeline that is always red carries no
signal**, and it would not have caught a genuine break here. Logged as **OI-80**, not fixed.

📌 **Not verified and it cannot be from here: a real browser click-through.** The Chrome extension has
failed to connect all week. The chain above (running-container source → live chunk contents → live API
payload) is the strongest proof short of a human opening the page. **Malik's UAT is the last step:**
add any meal and confirm the Add button reads *Choose chips* until one is picked, in the order
Heat → Chips → Drink → Dip.

<details><summary>Original OI-79 diagnosis, kept for the trail</summary>

## 🟡 2026-08-13. OI-79, DIAGNOSED FROM THE LIVE MENU DATA, NOT BUILT: meal tickets don't say which chips, because chips are an OPTIONAL group nobody has to pick.

Imran, WhatsApp 00:03 with a photo of ticket `260812-D008` (`#D006`, delivery, £98.36): *"It doesn't
say which chips on the meal here"*. The `Double Peri Peri Wrap Meal` line prints only `Hot Heat` and
`Rubicon Passion Fruit`. Malik: *"whatever's missing, its missing on the website checkout flow too."*

**Malik's own hypothesis was right and the live menu payload confirms it exactly.** All **25** meals
take their chips from a single group, **`Meal Deal Upgrade`**, which is
**`required=False, min_selections=0, max_selections=1`**:

| Option | Delta |
|---|---|
| **Regular Chips** | **+£0.00** |
| Upgrade to Large Fries | +£0.79 |
| Upgrade to Peri Peri Fries | +£0.99 |
| Upgrade to Large Peri Peri Fries | +£1.19 |
| Upgrade to Wedges | +£1.39 |
| Upgrade to Peri Peri Wedges | +£1.59 |

**There is no chips group anywhere else in the menu, and chips are never implicit.** Searched all 87
items: the only other chips modifiers are `with Chips` inside the four on-the-bone / boneless
`-- Choice` groups, which are required and therefore always print. So for a meal, if the customer does
not actively tick something in `Meal Deal Upgrade`, **no chips line exists on the order at all** and
the ticket correctly has nothing to print.

**Malik reproduced it himself without realising.** His basket screenshot shows
`Fish Burger Meal → 7UP, Regular Chips` (he ticked it) directly above
`Double Peri Peri Wrap Meal → Hot Heat, Rubicon Passion Fruit` (he did not). Same basket, same bug,
two lines apart.

⚠️ **The group's NAME is the trap, as much as the flag.** A customer reading *"Meal Deal **Upgrade**"*
correctly concludes they do not want an upgrade and skips it, believing chips are included, which they
are, since the meal price covers them. **The blank therefore always means "regular chips" in practice,
because nobody buys a meal wanting zero chips.** The kitchen simply is not told.

**Fix, data-only, no deploy, fixes the website and the POS simultaneously** because both read the same
menu API. `PATCH /api/v1/menu/modifier-groups/{id}`; `ModifierGroupUpdate` accepts exactly the fields
needed (`name`, `required`, `min_selections`), verified in `backend/app/schemas/menu.py:59`:
- `required` → `true`, `min_selections` → `1` (max stays 1)
- rename `Meal Deal Upgrade` → something that reads as a choice, e.g. **`Chips`**

**Cost: one extra tap per meal.** The storefront already enforces `min` properly, so nothing needs
building: `ItemModal.tsx:60` computes unmet groups, `:172` marks them `*`, `:271` disables Add and
`:279` labels the button `Choose chips`. **No new field and no new screen**, which matters against the
1-in-45 abandonment rate.

⚠️ **The tempting alternative is the wrong one: do NOT make the printer assume "Regular Chips" when the
group is empty.** That hardcodes a menu assumption into `print_service.py`, i.e. a rule re-expressed in
a second place, the exact shape that produced OI-61 / 65 / 66 / 68 / 73. Fix the data, not the paper.

**Not verified:** whether the admin Menu Management UI exposes `required` / `min_selections` (the API
does); whether the POS tablet's own `ModifierModal` enforces `min` the same way the storefront does;
and how many past orders carry a chips-less meal, which is a read-only production count nobody has run.

**Next action: Malik's call on making the group required. Nothing built, nothing changed.**

*Superseded 2026-08-13 02:30 PK: measured at 20.5%, approved, shipped and verified. See the block at
the top.*

</details>

<details><summary>OI-78 as authorised, before it shipped</summary>

## 🔵 2026-08-12. OI-78, AUTHORISED BY MALIK, BUILT BUT NOT YET DEPLOYED: the failure message lies to the customer.

Malik, on seeing the cause: *"the offline/bad signals version should not show this message at all. it
should clearly tell the customer that there is something wrong your internet connection. please
refresh/go to better signals zone etc"*. **This is a real defect independent of OI-77** and would have
made OI-77 self-diagnosing: had the screen said "we cannot reach our system", nobody would have spent
an hour on stale bundles and rural signal.

Three things wrong in the current storefront, all in the same failure path:
1. **The copy.** A shop live for two weeks tells customers *"Online ordering is coming very soon"*,
   which reads as "not launched yet". `Checkout.tsx:456`.
2. **No retry, ever.** `App.tsx:77` fetches the menu **once on mount**. One blip and the customer
   browses a full menu, builds a basket, and is only told at the **checkout total**. Only a manual
   reload recovers it.
3. **Discovery is too late.** Nothing on the menu screen warns them; the wall is the Pay button.

**Ships via `cd storefront && npm run deploy` (Cloudflare), NOT `git push`.** See
[[chick-shack-two-deploy-pipelines]]. **Deploy scheduled after the 22:00 close**, matching every prior
storefront deploy; the shop was open when this was authorised.

*Shipped 2026-08-13, Cloudflare version `f0d8764a`, with the copy corrected after Malik's catch. See
the block at the top.*

</details>

## 🟢 2026-08-10, live. `260810-D001` is missing from the tablet: DECLINED CARD, NOT ABANDONED. Money is clean.

Malik asked where today's order 0001 went. Answered from the production DB **and the live Stripe
API**, read-only, nothing changed. **This is a different failure mode from 08-07's `260807-D005`, and
the difference matters.**

- `260810-D001`, **Andy Napier**, delivery to *Lothlorien, Shore Road, Rahane G84 0QW*, **£26.17**,
  created **16:06:13 BST**. A live session exists and — unlike 08-07 — a **PaymentIntent does too**
  (`pi_3U2unMFnGj7KcDjJ1OivNSB4`). He entered card details. **The card was declined:**
  `payment_method_provider_decline` / **`insufficient_funds`**, paid via Link. PI sits at
  `requires_payment_method`, **`amount_received` 0, `amount_capturable` 0**; session still `open`.
  **No money was taken, nothing to refund, and correctly nothing reached the tablet.**
- **He immediately re-ordered and paid.** `260810-D002`, same name, same phone, same house, **11m25s
  later**, **£22.68**, authorised 16:18:02, captured 16:18:47, delivered. He **rebuilt a cheaper
  basket** to fit: D001 was `Fried Chicken £4.99 + Combo Fried Chicken with 2 Wings Meal £15.98`;
  D002 is `Fried Chicken £7.99 + Spicy Fried Wings £9.99` (*"Can you do mega spicy on the wings? Like
  inferno spicy please"*). **The shop lost nothing — same customer, same evening, £22.68 taken.**
- **Today in full: 5 orders, 4 paid, £88.51.** `D002` £22.68, `C003` £10.69, `C004` £30.67, `D005`
  £24.47 — all captured, accepted and completed. `D001` is the only gap.
- **All-time, every card basket that never authorised: exactly two.** `260807-D005` (abandoned before
  entering a card) and `260810-D001` (entered a card, declined). **2 in ~11 days.** Checkout is still
  not where this business leaks.
- ⚠️ **The predicted question arrived, as predicted.** The 08-07 entry warned that number gaps would
  keep generating it and that nothing on the tablet or the reports explains one. That is now twice in
  four days, with **two different causes**, and the gate behaved correctly both times. The unbuilt
  idea from 08-07 — surface an abandoned/declined count on the reports page — has a second data
  point behind it now. **Still not built and still not asked for.**
- 📌 **Incidental, and it corroborates OI-76:** D001/D002's address is a **named house with no number
  on Shore Road** (*Lothlorien*), the same road as the *"Aston Cottage, Shore Road"* in Imran's voice
  note. The named-cottage problem is recurring on one specific road, which strengthens the
  recommendation to **save the pin and directions against the customer record** — Andy Napier is now
  a repeat customer with a hard address, solved once, reused forever.

## 🔵 2026-08-10. OI-76 RESEARCHED, RECOMMENDATION FORMED. NOTHING BUILT, NOTHING SENT TO IMRAN.

Voice note 01:56 UK, transcribed locally. **Registered as OI-76.** Transcript at
`_context/clients/chick-shack-uk/voice-notes/2026-08-10_imran_what3words.md`. **Full research, costs,
licence findings, recommendation and the unsent draft reply:**
`_context/clients/chick-shack-uk/delivery-location-research_2026-08-10.md`.

Delivery radius is 20 to 25 miles of rural Argyll: named cottages, back roads, poor signal. That
night *"Aston Cottage, Shore Road"* could not be found in Google Maps **or in PostTag**, which they
already use, and the driver had to ask the customer to walk out to the road. He proposes
**what3words**, which he uses in his security business, and **explicitly asks for advice rather than
ordering a build** ("I don't know if you think this is a good idea").

**Researched 2026-08-10 against their published pages, nothing quoted from memory. Verdict: do not
buy the what3words API.**
- The **Free plan cannot do it** — AutoSuggest only, and AutoSuggest returns **no coordinates**.
  A pin needs `convert-to-coordinates`, which is paid. Basic **£7.99/mo** / 1,000 conversions would be
  ample at ~330 orders/month, so **price was never the obstacle**.
- **The licence is.** Clause **6.3(b)** forbids displaying a 3 Word Address *alongside its
  corresponding coordinates*; **6.3(e)(iii)** caps storage of the pair at **30 calendar days**. That
  rules out the obvious build. Storing the words **alone** is unlimited (6.3(e)(i)), so a plain
  optional text field costs nothing and stays compliant.
- **The conceptual point:** what3words solves a *speaking* problem, how one human transmits a location
  by voice. On our website nobody speaks, because the customer's phone already knows where it is. In
  Imran's security work both ends are trained staff with the app installed; a takeaway customer is a
  stranger who will not install one. His own *"how do we influence people to use this"* is the whole
  problem, and it is behavioural.

**Recommended instead, all free, in order:** (1) a driver-facing "how to find you" box, separate from
the kitchen note; (2) a "share my current location" button; (3) **save the pin and directions against
the customer record** so a hard address is solved once, the biggest compounding win for a takeaway;
(4) a map picker for the not-at-home case (Google Maps Dynamic Maps: **10,000 free calls/month**, then
$7/1,000, so free at ~3% of allowance; OSM's own tiles were rejected, their policy warns commercial
access "may be withdrawn at any point"). Malik confirmed the driver end is solved: orders reach the
driver's phone by WhatsApp or a shareable link.

⚠️ **Checkout friction is the real risk.** Abandonment is **1 basket in 45**. Anything added must be
optional, small, and never between the customer and the Pay button.

**Verified in the repo:** `Checkout.tsx` collects address + postcode + a box labelled "Notes for the
**kitchen**", and has **no driver-facing field at all**; **no customer detail persists between
orders** (every field `useState("")`; only the basket is stored); but orders **do** link to a
`Customer` row by phone via `_link_customer`, so (3) has its join already. Any storefront change is a
**Cloudflare deploy**, not `git push`.

**Next action: Malik picks what goes back to Imran. The draft reply is written and unsent. No build is
authorised.**

## 🟢 2026-08-10. Google review email. BUILT, DEPLOYED, SWITCHED ON (`5dda69f` + `2795ca2`)

Every online customer now gets one email asking for a Google review, **3 hours after the kitchen
accepts**, sent only between **09:00 and 22:00 shop-local** so nobody is emailed at 1am. Items
listed as text, no photo (the POS has no food photography). Rejected orders and abandoned card
checkouts never get one. **Live for `chick-shack` only**; the other two tenants are off because
`google_review_url` is NULL, which is the feature's own switch.

A background timer in the backend does the work, every 15 minutes, at most 25 emails a pass. No
cron, no Tailscale, no dependency on the shop's tablet being awake. The claim is an atomic
conditional UPDATE, so 4 uvicorn workers cannot double-email one customer.

🔴 **A real bug shipped in `5dda69f` and was caught minutes later, at switch-on:** the 12h staleness
cutoff and the 09:00 window left a dead zone that **silently binned every order accepted after
~19:00**, i.e. peak dinner. Both of 09 Aug's orders were queued to be dropped. Fixed to 18h in
`2795ca2`. **The bug lived in the gap between two passing tests** — see `_state/open-items.md`
OI-75 for the full lesson, which generalises: when two limits bound the same value from opposite
ends, test the interaction, not each limit.

**Verified live:** server at `2795ca2`, migration applied, both columns present, `18:00:00` read
back from inside the running container, sweep run in-process against production cleanly, 0 backend
exceptions, Orbit CRM untouched, all public URLs 200. **2 emails confirmed queued for the 09:00 BST
sweep** (`260809-D001` £42.20, `260809-D002` £11.69).

✅ **Confirmed working end to end, 2026-08-10 06:24 UTC.** Malik reviewed the two real rendered
emails first (artifact `82863eb1`), asked for first-name greetings and a Bcc to himself, then:
*"yes both emails fired accurately."* Both delivered to real customers, `260809-D001` and
`260809-D002`, with him copied. Greeting shipped as `Hi Howard,` / `Hi Gerardine,` (`52b1d1f`).

**The Bcc was for those two only and there is nothing to switch off.** `notify_customer` has **no
`bcc` parameter at all** and the sweep's source never mentions it, so the automatic path
structurally cannot copy anyone. Verified by reading the live signatures out of the running
container, not by reading the diff.

✅ **The background timer is proven to run on its own**, which nothing else could show (app-level
logs never reach the container log, OI-60, and there is no `pg_stat_statements`). A probe order was
armed on **demo-restaurant** (Asia/Karachi, so inside the send window while London was still
pre-09:00) with a **whitespace email address** — it passes the sweep's `!= ''` filter so the order
is claimed, but `send_order_email` strips it and returns before contacting the mail provider.
**The worker claimed it unaided 24 seconds later, at 06:37:06**, and zero emails were attempted.
Probe deleted, demo-restaurant's URL reset to NULL, no stray rows.

**Final state: `chick-shack` ON, `cosa-nostra` and `demo-restaurant` OFF.** All 8 containers
healthy, Orbit CRM untouched, 0 backend errors, 0 nginx 5xx, all five public URLs 200, and the
storefront's CORS still returns its own origin.

## 🟢 2026-08-09. Imran's QR code and a Google review link. DECODED AND VERIFIED WORKING.

Malik forwarded Imran's WhatsApp (23:09 to 23:19 PK): a red QR image, *"This qr code goes to menu /
On website"*. Malik asked *"do u want me to publish this on the website menu?"* and Imran replied
*"Yes please"*. Malik separately pasted a **Leave a review** link. Registered as **OI-75**. Nothing
built, nothing deployed. This entry is the verification only.

- **The QR decodes to `https://www.chickshackg84.com/`.** Decoded for real with `pyzbar`, after
  OpenCV's detector failed on the missing quiet-zone border. Read from **both** images Malik sent
  (the standalone JPEG and the QR inside the WhatsApp screenshot). Identical payload, so there is
  only one QR.
- **It works end to end, checked on the path a customer's phone actually walks:**
  - `www.chickshackg84.com` resolves (Cloudflare, same A/AAAA records as the apex).
  - `GET /` with a mobile UA returns **200**, no redirect, and it is the real storefront
    (`<title>Chick Shack, Order Online | Garelochhead</title>`, entry `index-D9lZ_Z-R.js`).
  - **CORS was the real risk and it passes.** `www.` is a *different origin* from the apex, and the
    storefront calls `https://eats.sitaratech.info/api/v1` cross-origin. Asserted with a real
    `Origin` header: `www.chickshackg84.com` gets
    `access-control-allow-origin: https://www.chickshackg84.com`, the apex gets its own, and an
    unknown origin gets **no ACAO header at all**, i.e. correctly restrictive.
  - Live menu payload right now: **GBP, 8 categories, 87 items, `ordering_paused: false`.**
- **"Goes to menu" is accurate.** The storefront has no router. `App.tsx` holds a single `view`
  state initialised to `"menu"`, so `/` *is* the menu. There is no better URL to point at.
- ⚠️ **The instruction as stated does not make sense, and it should not be built as literally asked.**
  Publishing a QR that points at the website **on** that same website means a customer already
  looking at the menu scans a code to reach the menu. The QR's value is **off** site: shopfront,
  counter, flyers, leaflets, delivery bags, Instagram bio. **Ask Imran where it is really meant to go
  before building anything.** The plausible readings are (a) he wants it printed and wants us to host
  the image, or (b) the thing that actually belongs on the site or receipt is the **review** QR.
- **There are TWO QRs. The second one, sent 23:27 PK, is the review QR.** It decodes to
  **`https://g.page/r/Ccxrn-XKIKecEBI/review`**, one character off the link Malik pasted (`...EAI`).
  **Same business**, proven by decoding both short codes: identical **CID `11288027046835350476`**
  (placeid `ChIJm7hKDaSpiUgRzGuf5cogp5w`). Only the trailing attribution byte differs (`0x1002` vs
  `0x1012`), which is just where Google was copied from, desktop profile vs mobile app card.
  **It is Chick Shack's profile, confirmed by Malik.** Either link works; pick one and use it
  everywhere so the review stats stay in one place.
- **The pair splits cleanly by purpose.** Menu QR is off-site acquisition (shopfront, counter,
  delivery bags, flyers, Instagram bio). Review QR is post-purchase (printed receipt, order
  confirmation screen, table card). That is the answer to "publish it on the website menu": the
  **review** QR is the one with a real home on the site.
- **Nothing on the storefront references a review link today.** Grepped `storefront/src` for
  `g.page`, `writereview` and `review`: zero hits. So a review prompt on `OrderConfirmation.tsx`
  would be new work, and it ships via a **Cloudflare deploy** (`cd storefront && npm run deploy`),
  not `git push`. See [[chick-shack-two-deploy-pipelines]].

## 🟢 2026-08-08. OI-73: the sales CSV called Chick Shack's pounds rupees. SHIPPED + VERIFIED LIVE (`5134430`)

Malik, from `https://eats.sitaratech.info/online-orders/reports`: the Daily Sales download read
`Total Revenue (PKR),371.07`, while the Prepaid vs COD download **from the same page and the same
date range** read `Prepaid Revenue (GBP)` and was correct. His instruction: **"all reports should be
tied to the tenant currency."**

- **Cause: the same standing mistake, a fifth time.** `backend/app/api/v1/reports.py`
  `export_sales_csv` hardcoded the literal `"(PKR)"` on all 13 money rows. `online_reports.py`
  (OI-58) resolves it properly through `public_order_service.get_currency`, which is precisely why
  one CSV was right and the one beside it was wrong. **A rule that already had one home, re-expressed
  inline somewhere else.** Same shape as OI-61/65/66/68.
- **The money was never wrong. Label-only.** `371.07` is the correct GBP figure; PKR and GBP both
  have 2 minor digits so the exporter's `/100` was right either way. Cross-checked: the prepaid CSV
  reports the same `371.07`, and 371.07/11 = the exported 33.73 avg order value.
- **The blast radius is small and was measured, not assumed.** The whole backend has **only two CSV
  exporters** and the other was already correct. The page's on-screen tiles were already correct too
  (`OnlineReportsPage.tsx` passes `config.currency` into `formatMoney`); `utils/currency.ts` is
  currency-aware and `configStore` sets it on fetch, so ReportsPage/AdminDashboard/ZReportPage never
  had this bug.
- **Verified (local dev container, 2026-08-08):** new `backend/tests/test_report_currency.py`, 4
  tests, both directions. A GBP tenant gets GBP on every money row and **no `PKR` in the file at
  all**; a PKR tenant still gets PKR and no `GBP`; a tenant with no config falls back to PKR rather
  than an empty `()`; order *counts* keep no currency suffix. **Mutation-checked**: putting one row
  back to hardcoded PKR fails the GBP test. Full suite **519 passed**, `ruff` clean on both touched
  files; the 10 failures + 2 errors are the parked QB-Desktop suite plus two others
  (`test_p1a_features::test_void_with_reason_succeeds`, `test_pay_first::test_transition_blocked_
  without_payment`) **confirmed failing identically on a clean-HEAD `git worktree` at `5b3dc00`**,
  run back-to-back in the same container. Zero regressions.
- ✅ **DEPLOYED 2026-08-08 ~07:40 UK / ~11:40 PK, commit `5134430`**, on Malik's "commit push deploy".
  Shop shut, ~8h before the 16:00 open, the same safe window every prior deploy used. Backend-only,
  so `git push origin main` alone shipped it and the Cloudflare storefront pipeline was correctly
  not run. Staged by explicit filename, 4 files; the ~125-file dirty tree and OI-60's untested
  backend work were left exactly as they were. Staged diff scanned for secret-shaped strings: **0**.
- **Verified live beyond the green Action, and this one got the strongest proof available.** Rather
  than reading the file on disk, `export_sales_csv` itself was **called in-process inside the running
  production container against the live database**, for all 3 active tenants, over Malik's exact
  07-08 Aug range:
  - `chick-shack` → `Total Revenue (GBP),371.07`. **PKR count 0, GBP count 12.** The precise row he
    downloaded as PKR, now GBP, **with the value unchanged**, which is the proof it was label-only.
  - `cosa-nostra` and `demo-restaurant` → still `(PKR)`, GBP count **0**. No collateral damage.
  - Server `git log` = `5134430`; backend/nginx containers freshly recreated and healthy; **Orbit CRM
    untouched** (`orbit_api` 8 weeks, `orbit_db` 2 months, `orbit_web` 3 months uptime).
  - Running container greps: hardcoded `Revenue (PKR)` → **0**, currency-resolved labels → 13,
    `get_currency` call present.
  - Public HTTPS with a browser UA: `/api/v1/health`, `/online-orders`, `/online-orders/reports` and
    `chickshackg84.com` all **200**. **0 backend exceptions, 0 nginx 5xx** since deploy.
- ⚠️ **A verification trap worth keeping:** the first 5xx check reported "4" and was **my own grep's
  fault, not an outage**. The pattern ` 5[0-9][0-9] ` matched the nginx **response size** `537`, not
  the status code. All four lines were `200 537`. Anchor on the status field (`" 5[0-9][0-9] `) or
  tally `grep -oE '" [0-9]{3} '`. The 3 remaining `400`s are empty request lines from the GitHub
  runner IP during its own verify step, i.e. deploy tooling, not user traffic.
- **Found but deliberately NOT fixed, logged as OI-74**, because changing screens nobody complained
  about is the OI-71 mistake: `qb/SyncTab.tsx` has its own local `formatPKR` hardcoding `Rs.`
  (latent, since Chick Shack has no QuickBooks), several admin *input* forms are labelled `(PKR)`, and
  both CSV exporters divide by a literal `100` which would be wrong for a 3-digit currency (KWD) or
  a 0-digit one (JPY) if a Gulf tenant ever lands.

## 🟢 2026-08-07. OI-65's last untested residual finally fired in production, and it behaved.

Malik asked why `260807-D005` was missing from the tablet (the queue jumped D004 to D006). **Answer:
it is an abandoned card checkout, and the gate hid it on purpose.** Read-only production query, no
change made:
- `260807-D005`, Derek Slee, delivery, £17.19, created **17:07:42 UTC**. A live Stripe session exists
  (`cs_live_…`) but **no PaymentIntent was ever created**, `payment_authorized_at` is NULL, and
  `updated_at` is 0.26s after `created_at`, so nothing has touched the row since. The customer
  reached Stripe and never entered card details. **No money was taken and there was nothing to cook.**
- **The publication path is provably alive in the same window**, so this is the gate working and not
  the gate stuck: D006, D007, D008, C009, C010, D011 and D012 all authorised and published either
  side of it.
- ⚠️ **This is the exact residual OI-65 flagged as never exercised** ("the negative case ... was never
  exercised against a real unpaid live session, because all 17 live sessions are complete/paid").
  It has now happened for real, on a live session, and the order correctly never reached the tablet.
  **Consider that residual closed by production.**
- **Abandonment rate, last 7 days: 1 of 45 card baskets** (0 on every prior day). Checkout is not
  where this business leaks customers, which is worth remembering during the OI-72 ads conversation.
- **Expect the numbering gaps to recur and to keep generating this question.** Order numbers are
  allocated when the basket is submitted, before payment, and OI-68 deliberately never re-issues a
  number. Every abandoned checkout therefore burns one permanently. Nothing on the tablet or the
  reports explains a gap today. Small idea, not built and not asked for: surface an abandoned count
  on the reports page so a gap has a visible reason.

## 🔵 2026-08-07. NEW, NOT STARTED: Imran wants a Meta ads experiment. Blocked at step zero.

Malik's framing: *"imran is proposing meta ads experiment to boost online ordering. we'll need to
first connect his fb/ig - get admin access."* Registered as **OI-72**.

**The blocker, in Imran's own words (WhatsApp, screenshot):** *"My meta ads account is restricted and
will not allow me to post ads"*, and when he tries to link the Instagram and Facebook page he gets
**"Your account is restricted. You're temporarily restricted from taking this action to protect
your profile. Please try again later."** Malik: *"ok lets brainstorm a way around then."*

✅ **2026-08-08, NOW DIAGNOSED from Imran's own Business Support Home screenshot (laptop). The
earlier "unverified, could be a temporary block" note is superseded.** It is **not** temporary and it
is **not** an ad-account-only problem. Meta shows, on his personal Facebook account (`Imran Rasul`,
`facebook.com/business-support-home/100004720803467`):
- 🔴 **`Account restricted`, "Restricted on 9 Oct"** (year not shown on the page, so **at least 10
  months old** if it reads 2025, which is the likely reading. Confirm before assuming an appeal
  window is open).
- Reason quoted verbatim: *"You're not allowed to use Meta Products to advertise. This is because you
  didn't comply with one or more of our Advertising Standards affecting business assets, such as
  having too many ads rejected, attempting to circumvent our ad review process, participating in
  fraudulent behaviour or associating with untrustworthy accounts."*
- Restrictions listed: **can't use or manage ad accounts · can't create or run ads · can't manage
  advertising assets or people for businesses**.
- Disabled assets: **Personal ad account**, **Audiences**.
- **The Chick Shack Page is NOT listed as a disabled asset**, and no Page-level or IG-level
  restriction appears. Unverified whether that holds on the assets tab, but on this page the Page
  looks clean.

**This also explains the "temporarily restricted" popup he saw when linking Instagram to the Page.**
That is the third restriction ("can't manage advertising assets or people for businesses") firing on
a Business-tools action, surfaced with Meta's generic profile wording. **One cause, two symptoms.**

⚠️ **Consequence for the plan: appealing is a lottery ticket, not the plan.** A 10-month-old
Advertising Standards restriction citing circumvention and untrustworthy association is Meta's
severe bucket and is rarely reversed. **The route that does not depend on Meta's goodwill is to run
ads from a clean ad account inside a separate business portfolio that Malik owns, with the Page
assigned to it.** Imran's profile never needs to advertise.

⚠️ **New risk this diagnosis creates, and it is Malik's exposure, not Imran's:** the notice cites
*"associating with untrustworthy accounts"*. Meta does propagate. **Any portfolio that takes on this
Page must be a throwaway dedicated to Chick Shack. Never the portfolio running goldennummbers /
postpaidplans ads.**

⚠️ **Do not build a second profile to route around it.** Meta links accounts by device, payment
method and IP; an evasion attempt risks the Page itself, which is the shop's actual asset. The
legitimate route is an appeal plus a properly-permissioned business portfolio.

**Verified technical gap, and it is the real work here: there is no measurement on the storefront at
all.** Grepped `storefront/` for `fbq`, pixel, `gtag`, `dataLayer` and analytics: **zero hits, the
only matches are base64 noise in `package-lock.json`.** So today a Meta ad can be run but **no order
can be attributed to it**. Before spending money:
- A Purchase event must fire **when Stripe authorises**, not at checkout start. Firing at checkout
  start is precisely the mistake that produced the **£98.96 vs £36.04** report scare (OI-66). The
  "is this order real" rule already lives once, in `backend/app/services/order_visibility.py`.
  **Ad reporting must import that rule, not re-express it** (the OI-61/65/66/68 standing note).
- The Stripe round trip is a **full page reload**; nothing survives it except what `lib/pendingOrder.ts`
  explicitly stashes. A browser-only pixel on the confirmation page will therefore under-report.
  Server-side **Conversions API**, fired from the same place that already sends the "order received"
  email on authorisation, is the shape that matches this codebase.
- Any storefront change ships via **`cd storefront && npm run deploy`** (Cloudflare), NOT `git push`.
  See [[chick-shack-two-deploy-pipelines]].

**Next action (2026-08-08): three read-only screenshots from Imran on the laptop he is already on:
(1) the "See accounts" list behind the *What you can do* panel, (2) whether a `Request review` /
`Disagree with decision` button still exists on the restriction detail, and (3) Page access roles in
Meta Business Suite.** Nothing else can be decided without (2), because it tells us whether the
appeal has already been spent. **Still no build, no ad spend, no storefront change.**

## 🟢 2026-08-06 — Stripe "webhook delivery issues [test mode]" email, closed, no code touched

Stripe emailed that `https://eats.sitaratech.info/api/v1/public/stripe/webhook` had failed 9
times since 2026-08-03, **in test mode**. Diagnosed from the repo, not the dashboard, then
confirmed by Malik directly in Stripe:
- A **sandbox-mode** webhook destination for this same URL was a leftover from dev (registered
  sandbox-first per OI-20/H-6, 2026-07-29). Once the server was switched to a live
  `STRIPE_SECRET_KEY` (2026-08-01), `stripe_service.verify_webhook`'s H-2 guard
  (`docs/STRIPE_HARDENING_CHECKLIST.md`) correctly rejects any event that doesn't match the
  key's live/test mode — so the orphaned sandbox destination could only ever fail from that
  point on. **By design, not a defect.**
- The **live** webhook destination (`live-wh`) is separate, was already proven working with a
  real captured payment on 2026-08-02, and Malik screenshotted it live-mode: **Active**, 4
  events subscribed, 3% error rate (background noise, not this incident).
- Zero impact on real orders at any point — Chick Shack doesn't use subscriptions or
  `checkout.session.completed` fulfillment (the two cases Stripe's email flags), and
  `publish_authorized_card_orders` polls Stripe directly so publication never depended on the
  webhook anyway (OI-65).
- **Fix: Malik deleted the sandbox destination in the Stripe dashboard.** Confirmed via
  screenshot — sandbox Webhooks tab now empty, live `live-wh` untouched. No server config, no
  deploy, no code change.

## 🟢 Raised by Malik 2026-08-05 — three observations, all SHIPPED + VERIFIED LIVE (`1043686`)

Registered as **OI-69 / OI-70 / OI-71** in `_state/open-items.md`. Malik picked the approach for each
before any code was written, then said *"please do clinical deployment of these changes, no scope
drift."* Deployed **2026-08-05 ~05:10 UK / ~09:10 PK — shop shut, ~11h before the 16:00 open**, so
no order was in flight and no customer or staff member saw a mid-service change.

**Verified live beyond the green Action** (this project's "verify the effect, never the exit code"):
- Server `git log` = `1043686`. All 5 POS containers freshly recreated and healthy. **Orbit CRM on
  the same box untouched** — `orbit_api` 7 weeks, `orbit_db` 2 months, `orbit_web` 3 months uptime.
- **Chunks resolved `index.html` → `index-_onDuR4-.js` → the chunks it actually imports**, never
  grepped from the assets directory (which accumulates every historical build). Live
  `OnlineOrdersPage-4zMLxHwu.js`: `Dip tubs` 1, `accepted ` 1, `timeZone` 2, `min ago` 1. Live
  `SwitchPage-DVOOtS-L.js`: `Sign out and switch` 1, `Currently signed in` 1.
- Public HTTPS with a browser UA: `/switch` 200, `/online-orders` 200, both chunks 200,
  `/api/v1/health` 200, and **`chickshackg84.com` 200** (untouched — no storefront diff, so the
  Cloudflare pipeline was correctly *not* run).
- **The load-bearing assumption was checked, not assumed**: live `restaurant_configs.timezone` for
  `chick-shack` really is **`Europe/London`** (GBP, `online_ordering_only=t`). Without that the
  timezone fix would silently fall back to the viewer's zone. `cosa-nostra` and `demo-restaurant`
  are `Asia/Karachi` and now render in *their* own local time too — a free correctness gain.
  ⚠️ Worth knowing: **there are 3 active tenants**, so the server's "only active tenant" login
  fallback no longer applies — a login genuinely needs a slug. That makes OI-69's Restaurant field
  necessary rather than theoretical.
- **OI-60's untested backend work did NOT ride along** — explicitly checked after the container was
  recreated: `--log-config` count in the running `start.sh` is **0**, and the server tree has no
  modified `backend/`, `scripts/`, `docker/` or `docker-compose.demo.yml` files. `DIP TUBS` still
  present in the running `print_service.py`, so yesterday's receipt fix is intact.
- **Zero backend errors and zero nginx 5xx** in the 12 minutes after deploy.
- Staged by **explicit filename** — 8 files. The ~119-file doc reorg, OI-60's 6 files,
  `StaffManagementPage.tsx` and `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` all remain uncommitted,
  exactly as before. Staged diff scanned for secret-shaped strings: **0**.

⚠️ **Not verified, and it cannot be from here: a real browser click-through.** The Chrome extension
has failed to connect every session this week, and the page is behind a login whose credentials the
assistant must not handle. The chain above (real function tests → live chunk contents → live config
value) is the strongest available proof short of Malik opening the page. **His UAT is the last step.**

### ⚠️ OI-71 ENDED IN A FULL REVERT (`5b3dc00`). Read this before the block below.

**Corrected 2026-08-07.** The block below describes `1e6bff3` as the fix. It was not the end of it.
Malik rejected that too, on sight: *"ur making it look like a freakin duplicate? dips vs dips tub?
what the hell confusion are u creating?"* The same dip rendered twice on one card, once as
`Algerian Sauce (Dip Tub)` under its item and again as `Dips to pack: 1 × Algerian Sauce`.
**`5b3dc00` reverts the tablet card to byte-identical with `d9f57e7`** (diffed against that revision,
not eyeballed); every dip helper is gone from `lib/orderDisplay.ts`, leaving only the OI-70 timezone
work, 16/16 passing. **The printed ticket still groups dip tubs and was never touched.**

**The lesson is not the one written below.** It is not "check the medium". It is that **the honest
answer to his original question was "receipts are already fine, this screen needs no change", and
the right move was to stop there.** A live screen was changed for no defect, the correction was
rejected, and the correction's correction made it worse. OI-69 and OI-70 were real bugs and stand.

### ⚠️ Malik's UAT found a real display defect in OI-71 — fixed and redeployed (`1e6bff3`)

**His words:** *"why are dip tubs showing so differently — its just the regular item. what abt its
price, why isnt it reflecting? i hope we are not screwing up with the total order value etc."*

**The money was never wrong, and this was checked against production rather than reasoned about.**
On `260804-002` the Peri Peri Wrap Meal carries `unit_price` **1198 = 999 base + 99 Garlic Mayo**,
and `line_total = unit_price × quantity`. The rule holds on every row of those orders (Fried Chicken
`499+200=699`, Half Chicken `999+50=1049`, Fillet Tower `1099+99=1198`). Malik independently
confirmed it from a sample cart: 2 Boneless Breast £11.49 + 99p dip = **£12.48**. The OI-71 commit
only ever filtered which modifier *names* render as text — `line.total`, `subtotal` and `total` were
never referenced. **Dip tubs are priced: 99p, or 79p for Ketchup and Mayo.**

**The display was wrong, and his reaction was the correct one.** Lifting dips into their own block
tore a priced modifier away from the item whose price contains it. On `260804-002` the Garlic Mayo
belongs to the Peri Peri Wrap Meal *further down the card*, so the block sat above two unrelated
meals reading `1 × Garlic Mayo` with no price — on a card where every other row carries a price,
that reads as a charge that lost its money.

**The mistake, worth keeping:** *a treatment that is right on the printed ticket is not automatically
right on screen.* On monochrome thermal paper a `DIP TUBS` heading reads as a picking list because
nothing around it has a price. On the tablet card everything does. **Same information, different
medium, different reading — check the medium before porting a layout across.**

**Fix (`1e6bff3`, deployed ~06:05 UK, still ~10h before the 16:00 open):** dips go back inline under
their own item where the 99p is self-evident; the roll-up survives as what it was always for — a
packing reminder — now styled and placed as an instruction beside the kitchen note (`Dips to pack:
1 × Garlic Mayo`), which cannot be misread as a purchase. **The printed ticket is untouched and
still groups them, which is right for paper.** Verified live: server `git log` = `1e6bff3`, chunk
resolved `index.html` → `index-DUhDUjWM.js` → `OnlineOrdersPage-BRANqxjG.js` containing
`Dips to pack` ×1 and `Dip tubs` ×**0**; `/online-orders`, `/switch`, `/api/v1/health` and
`chickshackg84.com` all 200; Orbit CRM untouched; **0 backend exceptions, 0 nginx 5xx**.

📌 **Correction to the timestamps above:** the first deploy is logged as "~05:10 UK" — the shell used
to read it lacked BST tzdata, so it was really **~06:10 BST**. An hour out, no consequence (both were
~10–11h before open). The app itself is unaffected: it formats via `Intl` in the browser, and the
BST case is explicitly covered by the helper tests (`19:56Z → 20:56` in summer, `19:56Z → 19:56` in
winter).

| # | What he saw | Verdict | Built |
|---|---|---|---|
| **OI-69** | No way to log out of `/online-orders` — "stuck in this window" | **Real, and a closed loop.** `/online-orders` sits outside both layouts, which own the only logout buttons; `/login` bounces an authenticated user to `/`, and `/` redirects back to `/online-orders` for this tenant. Only escape was typing `/admin`. | New bookmarked **`/switch`** route: sign out + clear the remembered shop + land on a login form with an optional Restaurant field. **Deliberately unlinked from the queue** so the shop's unattended tablet can never hit it mid-service. |
| **OI-70** | Wants Garelochhead local time, placed vs accepted | **Real, two defects.** No absolute time and no accepted time on the card at all; and `placedAt()` had no `timeZone`, so it rendered in the *viewer's* zone — right on the shop tablet by accident, silently +4/5h wrong on Malik's screen in Pakistan. | Card now reads `12 min ago · placed 19:56 · accepted 19:59`, every clock time from `config.timezone` (`Europe/London`). Pending keeps the relative age because it is what justifies the red/amber border. |
| **OI-71** | Dip tubs still under the parent item — "are receipts working?" | **Receipts were already fine — verified inside the running container, not assumed.** `DIP TUBS` roll-up live in `print_service.py` (server at `d9f57e7`, `grep -c` → 1). One-line gap in the tablet UI only. | Card now shows a `DIP TUBS` block with per-name counts and drops dips from the item sub-lines — same grouping and same `" (Dip Tub)"` suffix rule as the ticket. |

**Scope: tablet frontend only. Zero backend diff, zero storefront diff** — no payment, order-number,
email, ticket or reporting path is touched, so yesterday's clean day cannot be regressed by this.

**Verification actually run** (not claimed): `tsc --noEmit -p tsconfig.app.json` clean · `vite build`
clean · eslint **0 issues in every touched file** (the repo's 22 pre-existing problems are unchanged
and all in files not touched here) · the pure display helpers extracted to `frontend/src/lib/
orderDisplay.ts` and **bundled with esbuild and run for real** — 29/29 against real 2026-08-04 orders
(`C010`, `C011`, and Malik's 3× Fillet Tower screenshot), including GMT/BST, midnight rollover and a
bad-timezone fallback. **The runner's own process timezone was `Asia/Karachi`** — i.e. the bug's
actual conditions — and it still produced UK times. Both fixes **mutation-checked**: removing the
`timeZone` option fails 12 tests, counting dip occurrences instead of quantity fails 2.

> ⚠️ **Do not `git add -A` here.** The tree still carries OI-60's paused, **never build-tested**
> backend work (`backend/Dockerfile`, `backend/scripts/start.sh`, `backend/logging_config.json`) —
> `start.sh` gained `--log-config logging_config.json`, which would go to production untested and
> can break backend startup. Also uncommitted and unrelated: `StaffManagementPage.tsx` (+41),
> `QUICKBOOKS_PLAYBOOK.md`, `seed_demo_kitchen.py`, and the ~119-file doc reorg. **Stage by explicit
> filename**, exactly as session S did.


## 🟢 Where things stand at the end of 2026-08-04

**The shop's first full day on the fixed card flow: 11 online orders, all 11 paid, £349.72, zero
unpaid, zero rejected.** Verified against the production DB, not assumed. Every order was card, every
one captured. Malik's own read of the evening: *"rest of the day went smooth."*

| Order | Placed (UK) | Type | Total | Paid |
|---|---|---|---|---|
| `260804-001` … `-004` | 15:26–16:24 | mixed | £36.04 / £62.92 / £70.32 / £12.69 | ✅ |
| `260804-D005` … `-C011` | 16:46–19:56 | mixed | £15.67 … £20.86 | ✅ |

The switch from `260804-004` to `260804-D005` mid-service is the C/D numbering going live. **No
existing order number was rewritten** — by design.

**🔴 Resume here — nothing is broken; these are the open threads:**
1. **Imran/Malik UAT the pause button on the real tablet.** It is live but has never been pressed in
   anger. It needs a page refresh on the tablet to appear (new JS bundle, old one cached) — Malik hit
   exactly this and thought it was missing.
2. **OI-60 (backend log persistence) is still paused and uncommitted**, untouched since session Q.
   6 files written, not build-tested. See `_state/open-items.md` OI-60.
3. **OI-63 test flakiness is now understood but unfixed** — see the note at the bottom of this block.

### What happened on 2026-08-04 (sessions T, in order)

**1. OI-65 — the card gate, rebuilt as an actual rule.** Imran's screenshot showed order `260803-003`
reading "CARD — PAYMENT PROCESSING" while already accepted. Root cause: OI-61's gate was a `WHERE`
clause on the `pending` query only, and the tablet's ungated **All** tab still drew live Accept
buttons. `accept_order` had no server-side check at all. Money was never at risk — 16 card orders
across 02–03 Aug reconciled 1:1 against 16 live Stripe PaymentIntents, all `succeeded`.
- ⚠️ **My first attempt was rejected, correctly.** It gated only `pending` (repeating the same
  mistake) and papered over the hole with a "Waiting for the customer's card payment" panel on the
  All tab. Malik: *"'waiting for customer's card payment' is exactly what we dont want to show in
  POS… why are u putting in temporary hacks?"* **Lesson kept: when a rule is bypassed through an
  ungated view, close the view — never dress the hole up in the UI.**
- Final shape (`d3d1e7d`): gate on **every** queue state; hard server-side guard in `accept_order`
  (`CardPaymentNotConfirmed`); no grace window at all; poll-time Stripe re-check so publication never
  depends on one webhook; atomic conditional `UPDATE` for the publication claim; "order received"
  email moved to the moment Stripe approves. Tablet files reverted byte-identical to `1f55cf1`.

**2. The £98.96 report scare — the real money-display bug.** The reports screen showed £98.96 online
and "prepaid" revenue when only £36.04 had been taken. Two causes: both report queries summed
`Order.total` for every non-voided order, and "prepaid" meant `stripe_checkout_session_id IS NOT
NULL` — a session created the instant the customer reaches Stripe, paid or not.
- Fixed in `4e2fe5c`: prepaid now means `payment_captured_at IS NOT NULL`, and reports exclude card
  orders Stripe never approved, exactly as the tablet does.
- **Root cause of all three incidents in three days was the same**: the "is this order real" rule
  written in one place and not the others. It now lives once, in
  **`backend/app/services/order_visibility.py`** (`is_real_order()` / `money_actually_taken()`), and
  the queue, the reports and the prepaid split all import it. **Do not re-express it inline.**
- Same commit fixed the wording that caused the scare: an order on the tablet is now *always*
  Stripe-approved, so "CARD — PAYMENT PROCESSING" was false. Reads **`CARD APPROVED — DO NOT
  COLLECT`** with the held amount; ticket prints `*** CARD APPROVED ***`.

**3. Imran's two new features (`6378b67`).**
- **Pause online ordering** — one tablet button, stops collection and delivery together. Enforced
  server-side in `create_public_order` (HTTP 503, `OnlineOrderingPaused`), **not just hidden in the
  storefront**. While off the customer's whole checkout form — name, phone, address and the Pay
  button — is not rendered; they get Imran's exact wording with the phone number, on the homepage and
  at checkout. Orders attempted while paused are **lost by design** (Malik's explicit call).
  Default is ON. Turning OFF asks for confirmation; resuming is one tap.
- **C/D in online order numbers** — `260804-C001` / `260804-D002`, **one shared counter**.

**4. The counter race Malik caught (`99b6757`).** He spotted that a probe printed `-C006` and `-D006`
together and asked how two orders could share a number. The probe output was misleading (three calls,
nothing saved between them) — but he had found a real hole I introduced: with the C/D letter,
`count(*) + 1` could hand `C006` and `D006` to two simultaneous orders, and those are *different
strings*, so `uq_order_tenant_number` could not catch it either.
- Fixed: allocate from the **highest number already issued today** with the letter stripped (one
  sequence across both letters, and no rewind onto a number already printed when a row is voided),
  under a per-tenant `FOR UPDATE` lock so a read-modify-write cannot double-issue.
- Checked production first: **zero duplicate order numbers have ever existed.** Closed before it bit.
  The closest real case was `C010`/`C011`, 22 seconds apart — well outside the window.

### Verification standard actually met (not just claimed)
515 tests passing, failure list compared against a clean-HEAD `git worktree` — **zero regressions**.
`ruff` clean on touched files, `tsc`/`vite build` clean for tablet and storefront. Deploy verified by
reading symbols **out of the running application object**, resolving `index.html` → entry → chunk for
the frontends, and proving the queue gate end-to-end with a probe order that was rolled back.

### ⚠️ Two traps that cost time today — read before verifying anything
- **`/usr/share/nginx/html/assets/` accumulates every historical chunk** (uploads never `--delete`).
  Grepping the assets directory proves nothing. Resolve `index.html` → `index-*.js` → the chunk it
  actually imports.
- **~10 test failures are time-of-day dependent, not real** — the OI-63 UTC-vs-Europe/London boundary
  bug. They fail late at night and pass in the afternoon. **A baseline captured at 23:00 is not
  comparable to a run at 16:30.** Re-baseline at the same clock, in a worktree, before claiming
  regressions. Still unfixed; this is the honest explanation for the count moving 21 → 13 → 10.

**⚠️ Superseded — kept only for the lesson.** The session's FIRST attempt (`a7da2fb`) was a
workaround and Malik rejected it, correctly. It gated only `state="pending"` — inheriting OI-61's
original scoping mistake — and then papered over the resulting hole by replacing the tablet's
Accept/Reject buttons with a "Waiting for the customer's card payment" panel on the "All" tab. Two
things wrong with that: he never asked for the Accept button to change, and **a "waiting for card
payment" row in the POS is exactly what the rule exists to prevent** — an unpaid card order should
not be there to be labelled in the first place. Corrected in `d3d1e7d`: **the gate applies to every
queue state**, the two frontend files are reverted byte-identical to `1f55cf1`, the Accept button is
untouched, and the `awaiting_card_payment` field (which existed only to drive that panel) is gone.
**The lesson, worth keeping: when a rule is bypassed through an ungated view, close the view — do
not dress the hole up in the UI.**
**✅ OI-65 is BUILT, TESTED, DEPLOYED and INDEPENDENTLY VERIFIED LIVE** (commits `a7da2fb` +
`93876b1`, 2026-08-03 ~23:15 UK / 2026-08-04 ~03:15 PK, after the shop's 22:00 close so no order was
in flight). Full detail in `_state/open-items.md` **OI-65**.
**🔴 Next action: Imran/Malik's live UAT on tomorrow's real card orders** — specifically that a card
order now appears on the tablet only *after* Stripe approves, and that the customer's "order
received" email arrives at that moment rather than at checkout. Nothing else outstanding.

**Session T in one line (2026-08-04): Imran's screenshot showed order `260803-003` reading "CARD —
PAYMENT PROCESSING" while already accepted — i.e. OI-61's card-payment gate was bypassed in
production within a day of shipping. Root-caused against the real DB, audit trail and live Stripe
API; reconciled the money (clean, no loss, no double-charge); then rebuilt the gate as an actual
invariant per Malik's rule that a card order must not land in the POS until Stripe approves it, with
no timeout of any kind.**

- ⚠️ **CORRECTION to session S's claim below.** Session S described OI-61 as *"the structural fix, so
  staff can no longer act on money that isn't confirmed yet."* **That was overstated.** What shipped
  was a `WHERE` clause on `list_merchant_orders(state="pending")` only. The tablet renders
  Accept/Reject for any unanswered order on **every** tab, the "All" tab is ungated, and
  `accept_order` had no server-side guard at all. Production found the hole the next day. Session S's
  own "6 of 11 (55%)" figure did improve to **1 of 5 (20%)** on 08-03 — the fix helped materially, it
  just was not the guarantee it was written up as.
- **The money is fine, and this is verified, not assumed:** 16 card orders across 02–03 Aug ↔ 16 live
  Stripe PaymentIntents, 1:1, all `succeeded`, `amount_received == amount` on every one. Zero
  uncaptured, zero dangling authorisations, zero orphan charges, nothing to refund. `260803-003` was
  charged exactly once, correctly, by a late capture at 17:11:02. **This was a real defect but not a
  financial incident.** OI-61's *secondary* net (the amber "CARD — PAYMENT PROCESSING" banner instead
  of red "NOT PAID — COLLECT") is why it surfaced as a question from Imran rather than a second
  double-charge.
- **The 5-minute grace window was the deeper error and is now gone entirely.** It would not have
  saved this order regardless of the All-tab hole: it would have released it at 17:09:51, still 70s
  before Stripe authorised at 17:11:01. The customer spent 6m06s on the Checkout page; the window had
  been calibrated on one day's worst case (179s) and was exceeded the very next day.
- **Malik's rule, implemented literally:** cash/COD lands as-is (no payment to process); a card order
  lands only once Stripe approves, however long that takes. Enforced in three places rather than one
  — the queue filter, a hard `accept_order` guard (`CardPaymentNotConfirmed`) that closes the All
  tab / stale render / direct-API paths, and a poll-time Stripe re-check
  (`publish_authorized_card_orders`) so publication never depends on a single webhook delivery. The
  publication claim is an atomic conditional UPDATE so the webhook and the tablet's two 10s polls
  cannot all "win" and triple-email the customer.
- **The "order received" email moved to the authorisation moment** — it used to fire before the
  customer had even reached Stripe, which under a hard gate would promise food for an order the shop
  can never see. Cash on delivery is unchanged.
- **496 passed** (baseline 485 + 11 new), failure list byte-identical to clean HEAD via a throwaway
  `git worktree`, zero regressions. `ruff`/`tsc`/`vite build` clean. `authorization_for_session`
  verified against the **real live Stripe API**, not only mocks.
- **Deployed and independently verified live, beyond the green Action** (this project's own "verify
  the effect, never the exit code" rule), final commit `d3d1e7d`: server `git log` matches;
  backend/frontend/nginx containers freshly recreated and healthy; symbols read back **out of the
  running application object**, not the file on disk (`publish_authorized_card_orders` and
  `CardPaymentNotConfirmed` present, `awaiting_card_payment` confirmed **absent** from the live
  `MerchantOrderSummary` schema, `PENDING_QUEUE_PAYMENT_GRACE` genuinely **gone — 0 references in
  both `public_order_service.py` and `print_service.py`**, `mark_card_order_authorized` correctly
  async).
- **The tablet is back to its original bundle, proven by content hash.** The live `index.html` loads
  `OnlineOrdersPage-bINTpwNa.js` — the exact chunk that was live *before* this session. Vite's
  content hashing means an identical hash is proof the source reverted byte-for-byte. Confirmed in
  that chunk: `"Accept"` and `"Reject"` present, "Waiting for the customer" **0**,
  `awaiting_card_payment` **0**. ⚠️ Note for future verification: `/usr/share/nginx/html/assets/`
  **accumulates every historical chunk** (uploads never `--delete`), so grepping the assets directory
  proves nothing — resolve `index.html` → `index-*.js` → the chunk it actually imports.
- **Proven end-to-end against the live database with a real probe order**, then cleaned up: an unpaid
  card order (`stripe_checkout_session_id` set, `payment_authorized_at` NULL) was **invisible in all
  three states — pending, active AND all**; the instant `payment_authorized_at` was set it became
  visible in pending and all. Probe deleted and confirmed gone. This is the actual behavioural proof,
  not a code reading.
- ⚠️ **One residual, stated rather than glossed:** the *negative* case (an unpaid Stripe session
  returning not-authorised) is unit-tested and safe by construction — the gate keys off PaymentIntent
  **status**, and `requires_capture`/`succeeded` *are* Stripe's own statement that money is held — but
  it was never exercised against a real unpaid live session, because all 17 live sessions are
  `complete`/`paid` and manufacturing one means creating a session on Imran's live Stripe account.
  Offered to Malik as an explicit option; he chose to deploy without it. **Tomorrow's first real card
  order is therefore the true end-to-end proof of the negative path.**

---

**Session S in one line (2026-08-03): Imran reported (voice notes) a real double-charge — a
customer paid online but the ticket and "accepted" email both said NOT PAID because staff accepted
before Stripe's authorisation landed; staff took payment again on the card machine and had to
refund. Confirmed 6 of 11 card orders that day (55%) hit this same race. Fixed at the source: a
card order is now hidden from the tablet's pending decision queue until Stripe confirms
authorisation (or a 5-minute grace window passes), so staff can no longer act on unconfirmed money
— plus defense-in-depth (ticket auto-invalidation on payment-status change, a 3rd "CARD
PROCESSING" ticket/tablet state, late-capture re-sends the "accepted" email, email wording keyed off
`stripe_checkout_session_id` not `stripe_payment_intent_id`). Same commit also shipped a 70p flat
service fee, dip-tub ticket consolidation, and a Z-Report currency-on-direct-landing fix.**

- 18 new tests, 476 passed; 13 pre-existing failures confirmed unrelated via clean-HEAD `git stash`
  comparison done BEFORE writing any code (logged as **OI-63**, not fixed — likely a date-boundary/
  timezone bug in `online_report_service.py`, distinct from the older OI-59 SQLite `func.cast` issue).
- `pg_dump` backup taken first (`~/backups/pre_oi61_20260803_045556.dump`). Committed (`f06979f`),
  staged by explicit filename (not `git add -A`, to avoid sweeping in the ~119-file pre-existing doc
  reorg sitting uncommitted in the tree). Pushed and deployed both pipelines — backend/tablet via
  `git push` (GitHub Actions, server `git log` matches, new code grepped directly out of the running
  container) and storefront via `cd storefront && npm run deploy` (Cloudflare, live bundle
  byte-identical to the local build, contains the new "Service Fee" line).
- **Malik's own retry/fallback idea and Imran's "pause accepting orders" toggle idea were
  deliberately NOT built tonight** — logged as **OI-62** for later scoping, not rushed on a live
  payments system under time pressure.
- **New priority raised in the same session, not yet started**: Malik is travelling and unavailable
  today, Imran is off, and the shop is staffed by people unfamiliar with the system. He wants a
  couple of hours of stress testing to confirm the card-payment flow works end to end before trusting
  it unsupervised. He has no live card and floated Stripe test/sandbox mode without disturbing the
  live storefront (`chickshackg84.com`, real orders, live Stripe keys) — asked for a concrete plan,
  not just validation of the idea. Full options already scoped in
  `PAUSE_CHECKPOINT_2026-08-03.md`'s Pending section: direct-API test bypassing the storefront,
  local dev's Stripe-key situation, whether real production traffic already exercises the fix enough
  to skip a synthetic re-test. **This is the next action.**

---

**Session Q in one line: Malik asked to double-check the card-payment flow for a specific loophole
("do we ever assume the customer has paid when he hasn't?"). Traced the whole pipeline (tablet,
ticket, email, confirmation page) and confirmed no such loophole exists — all four independently key
off the same server-derived `payment_status`, which only flips to `paid` via a real captured Payment
row. Found one real, narrower gap instead: a race between the shop answering an order (Accept/Reject)
and the customer's card finishing authorisation — fixed and deployed, commit `dfc88e9`. Also added a
durable Stripe audit trail per Malik's request ("keep all logs ... so any dispute can easily be
addressed"). Malik explicitly said "yes commit push deploy live" before any of this happened. Deploy
verified live beyond the green Action — see below.**

- **The race window**: `accept_order`/`reject_order` only ever act on a Stripe PaymentIntent that
  already exists at the moment they run. If staff tap Accept/Reject while the customer is still
  entering card details, there is nothing yet to capture/cancel — correct, falls through as an
  ordinary unpaid order (tablet shows "NOT PAID — COLLECT"). But if the authorisation then lands a
  few seconds later, nothing was previously watching for it: the hold just sat there until Stripe
  auto-expired it days later (no revenue loss or double-charge risk, but a dangling, unreconciled
  authorisation and potential customer confusion). **Fixed**: `reconcile_late_authorization()`,
  triggered from the same `payment_intent.amount_capturable_updated` webhook event that already
  backfills the intent id, closes it symmetrically — captures if the order was already accepted
  (kitchen already committed to the food), releases if already rejected, no-ops if still pending or
  already captured. A late capture that itself fails is logged loudly (`stripe_capture_failed`) as an
  unavoidable, human-needs-to-know case — food already made, card genuinely declined at the capture
  moment, cannot be fixed programmatically.
- **Durable Stripe audit trail**: every Stripe transaction now writes to the existing `audit_logs`
  table (tenant-scoped, queryable by `entity_id` = order id) — checkout session created, capture on
  Accept, cancel on Reject, and every webhook delivery received, *including* `payment_intent.canceled`/
  `payment_intent.payment_failed`, which deliberately change nothing on the order but are still real
  events a dispute conversation may need evidence of. Each row carries the Stripe event/intent id,
  amount, and who did it (staff user id for Accept/Reject, "Stripe webhook" for automated events).
  **Caveat**: DB-only for now, no viewer page — look it up via `make psql` filtering
  `entity_type='order' AND entity_id=<order id>` until/unless a report UI is asked for.
- 9 new tests (functional: late-capture, late-cancel, still-pending no-op, no-double-capture-on-
  replay, failed-late-capture; audit: checkout/accept/reject/webhook-event logging). Full suite:
  **479 passed**, same 14 pre-existing unrelated failures as session P (2 session-O + 12 QB-Desktop/
  parked) — zero new regressions, exact expected delta. `ruff check` clean.
- **Deployed and independently verified live, commit `dfc88e9`.** `git push origin main` (backend-
  only, no `storefront/` changes). "Deploy to Production" Action green including its own "Verify
  deployment" health check. Independently confirmed beyond the green Action: SSH'd in, `git log` on
  the server matches `dfc88e9` exactly, `pos-system-backend-1` freshly recreated and healthy; **the
  new code was grepped directly out of the running container** (`reconcile_late_authorization` present
  in `/app/app/services/public_order_service.py`, plus the new `stripe_checkout_created`/
  `stripe_capture_failed` audit action strings) — not assumed from the diff.
- **Next action for the Stripe fix itself**: nothing outstanding. The fix is dormant until the
  specific race timing occurs again in production; no live UAT step is needed (it is not a UI-visible
  feature).

## 🔴 Resume here — session Q paused mid-task 2026-08-02, two open threads

1. **Imran email check → found the real production log-retention gap → OI-60 opened → paused
   mid-build, on Malik's instruction, to write this down properly before continuing.** Full detail,
   design, and an exact done/pending file checklist: `_state/open-items.md` **OI-60**. Short version:
   - Imran said he placed two dummy test orders (collection + delivery) and didn't get an email for
     one. Checked the DB directly: the delivery order's email was typed `imzyyr@gmail.con` (missing
     the "m"), the collection order's was correct. **Not a code bug** — confirmed the email-send path
     has no service-type branching at all, and told Malik so.
   - That check needed yesterday's backend logs, which were already gone — the container had been
     recreated by this same session's own earlier deploy. Root cause: `backend`/`nginx` are
     `read_only: true` with no persistent volume, and both are recreated on every `git push`, so
     `docker logs` history resets on every deploy (this repo deploys several times a day).
   - **OI-60a (backend fix) is fully designed and all 6 files are WRITTEN, but UNCOMMITTED** —
     `backend/Dockerfile`, `backend/logging_config.json` (new), `backend/scripts/start.sh`,
     `docker-compose.demo.yml`, `docker/logrotate/pos-backend.conf` (new), `scripts/deploy-remote.sh`.
     The logging dictConfig was validated directly (`logging.config.dictConfig()`, not just read) and
     one real duplicate-handler bug was caught and fixed before it ever reached a container. **Not yet
     build-tested against the real Dockerfile** (local dev compose uses a different `Dockerfile.dev`,
     so it won't exercise these changes) **and not committed/pushed/deployed.** OI-60's checklist in
     `_state/open-items.md` has the exact resume point — read it before touching these files again,
     don't rediscover the design from scratch.
   - **OI-60b (nginx) is deferred and not started at all**, deliberately — nginx is shared with Orbit
     CRM and this box has two prior nginx-recreation outages on record. Treat as fully separate,
     re-derive its specific design (don't assume OI-60a's UID/handler approach transfers as-is).
2. **Stripe went LIVE and was proven with a real transaction, 2026-08-02 (verbal from Malik + Imran,
   cross-checked against our own DB — not yet independently re-verified by this session against a
   fresh read after the fact).** Malik set the 3 live values (`STRIPE_SECRET_KEY`, `STRIPE_
   PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`) directly on the server himself (values never passed
   through the assistant — verified only by safe prefix-count checks, e.g. confirming the running
   container's key starts `sk_live_`, never printing it). Real order `260801-004` (collection, £2.78,
   Imran's own card) was placed via the existing `?card=1` test override and accepted — **captured
   for real**, confirmed three ways: Stripe's own live dashboard (Mastercard •••5881, "Succeeded")
   and its "first payment" email, our `orders`/`payments` tables (matching amount and PaymentIntent
   id), and this session's own new audit trail (`stripe_checkout_created` with a `cs_live_...` session
   id → `stripe_captured` → `stripe_webhook_payment_intent.succeeded` landing 2s later, proving the
   live webhook registration is genuinely working end to end, not just Accept's own direct capture).
   **Imran approved going fully live, in writing (WhatsApp, shown to the assistant):** "Yes please...
   Ready to go live tomorrow... we will see how things are."
   - **Three things Imran asked for in the same message, now being built (2026-08-02, still same
     session): make the card option live, remove the "under testing" banner, and add a delivery
     cut-off mechanism.** Voice-note feedback on the third item was transcribed locally
     (`faster-whisper`, matching the established pattern from session K) — see
     `_context/clients/chick-shack-uk/voice-notes/` for a written copy once saved. Requirement:
     online delivery stops being taken at **21:30** for every delivery area except **Garelochhead**
     (**21:45**) — confirmed against the real `delivery_areas` table, not guessed from the mis-
     transcribed "gear lockhead". Collection is unaffected, stays open to the shop's normal 22:00
     close. **Malik corrected the assistant's first proposed design** (hiding the delivery option
     entirely) — the actual ask: reuse the *existing* pre-order pattern (`lib/delivery.ts`
     `orderTiming`/`isOpenNow` — "closed, opens at 16:00, your order will be accepted then, and
     you'll get a confirmation email") but trigger it for delivery specifically at the earlier
     cut-off, not just at the shop's overall close time. No backend/DB change expected — delivery
     areas and shop hours are both plain storefront config (`storefront/src/data/menu.ts`), not
     API-fetched.
   - **Malik's own words, explicitly expected and fine, not a bug if seen:** deploying this outside
     current opening hours means any real order placed overnight will correctly show as a pre-order
     and get "accepted when the restaurant opens tomorrow" — that is the intended behavior, not a
     regression.
   - **⚠️ Malik then corrected the design a second time** (his message: "no dont remove the delivery
     option - that will cause confusion"). Final, actually-being-built behavior: the delivery option
     stays visible always. Past its cut-off (or before opening, or after the shop's general close),
     it gets the SAME "closed, opens at 16:00, accepted then, confirmation email coming" pre-order
     treatment already used shop-wide — never hidden, never a separate refusal path.

## 🔴 Resume here — session Q paused via /handoff mid-build 2026-08-02, THREE threads

**A — delivery cut-off + card-live + banner-removal feature: CODE MOSTLY WRITTEN, UNTESTED,
UNCOMMITTED.** 7 storefront files touched (`git status --porcelain -- storefront/src` confirms
exactly these, nothing else): `types.ts`, `data/menu.ts`, `lib/delivery.ts`, `lib/pendingOrder.ts`,
`components/Checkout.tsx`, `components/OrderConfirmation.tsx`, `App.tsx`. What's actually done vs
not — **read this list before touching these files, don't rediscover the design:**
- [x] `types.ts` — `DeliveryArea.closeTime?` (per-area override) + `ShopConfig.deliveryCloseTime`.
- [x] `data/menu.ts` — `deliveryCloseTime: "21:30"`; Garelochhead's entry gained `closeTime: "21:45"`.
- [x] `lib/delivery.ts` — `orderTiming(now, service?, areaId?)` extended (backward compatible,
      existing no-arg callers still work), returns a new `closedReason: "shop_closed" |
      "delivery_cutoff"` field. New private `deliveryCloseTimeFor(areaId)` helper.
- [x] `components/Checkout.tsx` — `timing` now computed from live `service`/`areaId` state (was
      shop-wide only); pre-order banner copy branches on `closedReason` + now promises the
      confirmation email; `onPlaced`/`savePendingOrder` signatures extended to carry `timing` through
      (needed because the Stripe round-trip is a fresh page load — nothing survives except what's
      explicitly stashed).
- [x] `lib/pendingOrder.ts` — `Stashed`/`savePendingOrder`/`takePendingOrder` all carry `timing`
      alongside the order now; **`takePendingOrder`'s return shape changed** from `ApiOrderResponse |
      null` to `{ order, timing } | null` — this is the one signature change most likely to bite if
      re-derived from memory instead of read.
- [x] `App.tsx` — new `timing` state threaded through `onPlaced`/the Stripe-return effect/
      `OrderConfirmation`/`onDone` reset. `restored` (from `takePendingOrder`) updated for the new
      `{order, timing}` shape.
- [x] `components/OrderConfirmation.tsx` — takes `timing` as a required prop instead of calling
      `orderTiming()` itself (avoids a second, possibly-different computation after time has passed);
      copy updated to branch on `closedReason` + mention the confirmation email, matching Checkout's.
- [x] **`tsc`/`vite build` — DONE, session R (2026-08-02).** `tsc --noEmit` clean, `vite build` clean
      (46 modules, no errors) — the Checkout↔App↔OrderConfirmation↔pendingOrder prop/return-shape
      wiring is consistent.
- [x] **Manual verification of the cut-off math — DONE, session R.** Bundled `delivery.ts` with
      esbuild and ran the real `orderTiming()` (not a reimplementation) against 18 real-clock-time
      cases in `Europe/London`/BST: pre-order window open (14:00), shop open/close (16:00/22:00),
      21:29/21:30 non-Garelochhead delivery cutoff, 21:44/21:45 Garelochhead's own later cutoff,
      collection unaffected through to 22:00, overnight pre-order, and both backward-compat fallback
      paths (no `areaId`, no `service` at all). All 18 matched the intended design exactly — cutoff is
      inclusive (>=), collection only stops at the shop's general close, Garelochhead's 21:45 override
      is respected.
- [x] **`cardPaymentEnabled: true` flip — DONE, session R** (`data/menu.ts` ~line 567).
- [x] **"Under testing" banner — REMOVED, session R** (`App.tsx`, was lines ~97-112; the sticky
      header wrapper itself was kept, only the banner `<div>` and its comment were deleted). Rebuilt
      after both changes — `tsc`/`vite build` clean again, and the built `dist/` bundle greped clean
      of the "under testing" string.
- [x] **DEPLOYED AND VERIFIED LIVE, 2026-08-02 ~18:00 PK / ~14:00 UK, commit `678cdde`.** Malik
      pinged with explicit go-ahead ("we can initiate the deployment. over to u") after his ~2hr gap.
      Committed the 7 storefront files only (not the unrelated, still-unfinished OI-60 backend files),
      `git push origin main`, then `cd storefront && npm run deploy` (`vite build && wrangler deploy`
      — Cloudflare Workers, separate pipeline from the DO backend). **Verified beyond the exit code**:
      live `index.html` references the exact just-built bundle hashes (`index-a54c_nbI.js`/
      `index-iaUHhEfe.css`); the live JS bundle fetched from `chickshackg84.com` is **byte-identical**
      to the local build output (194,249 bytes, `diff` clean); the "under testing" banner string has
      **zero occurrences** in the live bundle. Both `chickshackg84.com` and `www.chickshackg84.com`
      serving the new version. **Real customers now see the live card-payment option, the delivery
      cut-off (21:30/21:45 Garelochhead) is active, and the testing banner is gone.**
- [x] **"Stripe Reconciliation" mismatch — INVESTIGATED, CONFIRMED, and the underlying test orders
      CLEANED UP, session R (2026-08-02).** Confirmed against the real DB (not just STATE.md prose):
      `260801-002`/`-003` had `cs_test_...` checkout session ids, created 17:48/19:21 UTC on
      2026-08-01 — before the live key went on the server at ~20:01 UTC that same day (right before
      `260801-004`, which has `cs_live_...`). Stripe correctly refuses to find a test-mode
      PaymentIntent via a live key — expected behavior, not a money-safety bug (`cardPaymentEnabled`
      was `false` for real customers the entire time Stripe was in test mode, so these could only have
      been internal `?card=1`-override tests, never a real customer). **Malik then asked to clear
      test orders for a clean slate.** Pulled all 17 orders ever placed for the tenant, classified
      them, and got his explicit scope: pg_dump backup taken and verified (42 tables, `orders` table
      confirmed present) → checked for `inventory_transactions` FK blockers (none) → deleted 11 orders
      (`260729-001/002/003`, `260730-001`, `260731-001/003/004/005`, `260801-001/002/003`) plus 3
      orphaned `audit_logs` rows tied to `260801-003`, in one transaction, verified via row-count
      output (`DELETE 3` / `DELETE 11`) and a post-delete re-query. **Deliberately kept, per Malik's
      explicit choice**: `260801-004` (the one proven real-money live capture — now the only
      `payment_status='paid' AND stripe_payment_intent_id IS NOT NULL` row left, confirmed by query —
      reconciliation will now show 1 checked / 0 mismatches), plus 4 orders with real-looking UK
      customer details (Jill Cochrane `260730-002`, Daisy Glover `260730-003`, Gregg Ross `260730-004`,
      Rachel Mccoll `260730-005`, all `voided`) that were NOT confirmed as test data — left untouched,
      not silently assumed to be test orders.
- [ ] **Separately flagged, not yet acted on: `260731-002` ("Leanna") is sitting `in_kitchen`,
      unpaid, since 2026-07-31 20:01 — neither voided nor completed.** Not part of the cleanup scope
      (real-looking customer details, same ambiguity as the 4 kept-voided orders above). May be a
      genuinely unresolved real order Imran's team never closed out — worth asking him about, not
      assumed either way.

**B — Malik asked (2026-08-02) whether deployment can be scheduled automatically for "tomorrow",**
since that's when Imran said he's ready to go live, rather than needing a live session at the exact
moment. **Not yet investigated or answered.** Real considerations for whoever picks this up:
`schedule`/`CronCreate` tooling exists and could fire `cd storefront && npm run deploy` at a set
time, but `DEPLOYMENT_PLAYBOOK.md` is explicit that a storefront deploy is "the UAT trigger... run it
only when he is at the tablet and expecting it. Time it with him" — "tomorrow" is not a time. Get an
actual HH:MM from Malik/Imran before building any automation, and confirm whether Imran wants to be
online watching at that exact moment (matching how the live Stripe test itself was coordinated) or is
genuinely fine with an unattended scheduled push.

**C — OI-60 (backend log persistence) is still separately paused from earlier in this same session,
untouched since.** See the OI-60 entry above and `_state/open-items.md` — unrelated to A/B, don't
conflate.

---

**Session P in one line: OI-57 (online-orders date filter/pagination/sort) and OI-58 (Chick Shack
reporting) are both BUILT, tested, and DEPLOYED to production, commit `55ac6de`. Malik confirmed
"commit and push" explicitly before either happened. Deploy verified live, not just green CI — see
below. Awaiting Malik's UAT.**

- **OI-57 built**: `list_merchant_orders` gained `date`/`date_from`/`date_to`/`offset`/`sort`
  (shop-timezone-aware day bounds, same fallback pattern as `print_service._offset_minutes`);
  `MerchantQueueResponse` gained `total_count`/`offset`/`limit`/`sort`; `OnlineOrdersPage.tsx` got a
  date picker, pagination controls and a sort toggle for Active/All (Pending's FIFO default kept,
  exactly as flagged for UAT). 8 new backend tests reproduce the exact reported bug and prove it
  fixed. Curl-verified against the known 7-orders-from-2026-07-28 local dataset: today-only default
  correctly shows 0 pending, an explicit `date=2026-07-28` correctly shows the 5 unaccepted ones,
  pagination and both sort directions all hand-checked.
- **OI-58 built, all four reports, in priority order**: fixed the mechanism first —
  `get_sales_summary` now exposes `online_revenue`/`online_orders` (was computed then silently
  discarded) and `get_live_operations` gained an `online` bucket, both platform-wide fixes, not
  Chick-Shack-only. New lean route `/online-orders/reports` (`OnlineReportsPage.tsx`), ink/flame/
  ember branded, shop name from `useConfigStore` (never hardcoded). Daily Sales reuses the
  now-fixed sales-summary endpoint; Prepaid vs Cash-on-Delivery and Rejected Orders are new
  dedicated queries (`online_report_service.py`); Stripe reconciliation (built last, per Malik's
  "maybe") added a read-only `stripe_service.retrieve_payment_intent` and degrades to an error row
  instead of a 500 when Stripe isn't configured (confirmed live in local dev, which has no Stripe
  key). 19 new backend tests. Curl-verified against real Postgres with a hand-built prepaid/COD/
  rejected order trio; every CSV actually downloaded and its content read, not just status-checked.
- ⚠️ **Real, separate bug found and deliberately NOT fixed (logged, not silently absorbed)**: this
  whole project's `func.cast(Order.created_at, Date)` report date-filter pattern is silently
  unverifiable by the backend's own pytest suite (SQLite casts it to a bare integer year, which can
  never compare true against a date bound) — every date-ranged report test that has ever passed did
  so with zero real orders behind it. Production is unaffected (real Postgres casts correctly,
  confirmed live). New OI-58c/d queries were written with plain datetime-range comparisons
  specifically to avoid inheriting this. Full root-cause in `ERROR_LOG.md` 2026-08-01, tracked as
  **OI-59** (low priority, not scheduled).
- Backend suite: **470 passed** (450 baseline + 19 new + 1 fixture change), same 2 pre-existing
  unrelated failures from session O plus the same 12 QB-Desktop/parked ones — nothing new broken.
  `tsc`/`vite build`/eslint clean for `frontend/`.
- **Browser click-through of the new UI was not possible** — the Chrome extension still will not
  connect, consistent with every session this week (see session L/M/N notes below) — verified
  instead via the production build output and by calling the exact same API endpoints the page
  calls, with hand-checked responses.
- **Deployed and independently verified live, commit `55ac6de`.** `git push origin main` (single
  pipeline — no `storefront/` changes this session). "Deploy to Production" Action green including
  its own "Verify deployment" health check (no transient 502 this time). Independently confirmed
  beyond the green Action, per this project's own "verify the effect, never the exit code" rule:
  SSH'd in, `git log` on the server matches `55ac6de` exactly, all 5 containers healthy/freshly
  recreated; the 6 new `/reports/online/*` routes are genuinely registered inside the running
  backend (checked via `app.routes`, not assumed from the diff); the live frontend bundle contains
  `OnlineReportsPage-3KnZgxlW.js` — **byte-identical chunk hash to the local build**, not just "a
  file exists"; and all 5 new/changed endpoints called for real over the actual public HTTPS domain
  (`eats.sitaratech.info`, with a browser User-Agent — nginx 444s bare curl-style clients here) came
  back `200` with exactly the expected new response shape (`total_count`/`offset`/`limit`/`sort` on
  the queue; `online_revenue`/`online_orders` on sales-summary; the three new online-report bodies).
  `Deploy to Staging` (AWS) failed identically to every prior push — confirmed pre-existing, not a
  regression from this deploy.
- **Next action: Malik UATs both OI-57 and OI-58 live** at `eats.sitaratech.info/online-orders` and
  its new "Reports" button. Nothing else is outstanding from this session's own work.

---

**Session O in one line: all 4 of session N's pending UX/polish items are built, tested and pushed — email wording, bold PAID ticket line, COPY-line removal, and a genuinely different (not just louder) chime technique. Awaiting Malik/Imran's live retest, the chime especially.**

- **Item 1 — "order received" email now says "Prepaid by card" for a card order, not "Payable on delivery".** Root cause, confirmed by reading the actual call order: this email fires inside `POST /orders`, synchronously right after the order is created — **before** the frontend even makes its separate `checkout-session` call, so `stripe_payment_intent_id` is structurally never set yet at send time for ANY order, cash or card. The email's existing 3-branch `_payment_status_text()` could therefore never render its "card held" branch here; it always fell through to the cash wording. Fixed without a DB migration: `PublicOrderCreate` gained a request-only `payment_method: "cash"|"card"` field (the storefront already tracks this client-side, in `Checkout.tsx`'s `payment` state, before submission) that threads through `notify_customer` → `send_order_email` → `_html_received`/`_body_received` as `intends_card_payment`, used only to pick the email's wording — never persisted, never used for any payment-correctness decision. Real Stripe state (`payment_status == "paid"`, or an authorised-not-captured intent) still takes priority over the stated intent if this function is ever reused elsewhere. 6 new/changed tests.
- **Item 2 — receipt's "PAID ONLINE" line is now `bold=True, big=True`**, matching "NOT PAID"'s existing weight (`print_service.py`, `_render_copy`). New byte-level test asserts the `SIZE_DOUBLE + BOLD_ON` prefix.
- **Item 3 — "COPY n OF 3" removed entirely from the printed ticket** (Imran: all three copies go to separate stations, none is "the extra one"). The daily `#NNN` double-size line directly above it is untouched. Cleaned up the now-dead `copy_number`/`copies` params on `_render_copy`.
- **Item 4 — chime rebuilt with a different technique, not just more gain** (`OnlineOrdersPage.tsx`, `playAlertTones`): square wave (was sine), two unison oscillators per tone (one an octave up), a short attack + near-peak hold instead of a smooth exponential ramp, a shared `DynamicsCompressorNode` so the extra layered energy comes out louder instead of clipping, and a 3rd repeat pass (was 2). **Cannot be verified for real perceived loudness from this environment — needs Malik/Imran on the real tablet, this is the next ask.**
- Backend: 450 passed, `tsc`+`vite build`+eslint clean for both `frontend/` (tablet) and `storefront/` (storefront has no eslint config, confirmed pre-existing). **Two test failures surfaced that are NOT from this session's diff** — `test_p1a_features.py::TestVoidHardening::test_void_with_reason_succeeds` and `test_pay_first.py::TestPayFirstTransitionBlock::test_transition_blocked_without_payment` — confirmed by `git stash` on exactly this session's touched files, re-running both against unmodified HEAD, and getting the identical failures; stash was popped back immediately. Not fixed (out of scope), logged in `ERROR_LOG.md` 2026-08-01 session O for whoever picks these up. The documented 12 pre-existing QB-Desktop/parked failures are unaffected either way.
- **Both deploy pipelines shipped and independently verified live, 2026-08-01, commit `f450da9`.** `git push origin main` deployed the backend + `frontend/` tablet app — "Deploy to Production" Action green including its own health check (no transient 502 this time), and independently confirmed inside the freshly-recreated `pos-system-backend-1`/`pos-system-frontend-1` containers: `email_service.py` has "Prepaid by card", `print_service.py` has no "COPY" and `PAID ONLINE` is `bold=True, big=True`, and the live `OnlineOrdersPage-CkRgTwiX.js` chunk contains `createDynamicsCompressor`/`square` — same content hash as the local build. Separately, `cd storefront && npm run deploy` shipped `Checkout.tsx`/`api.ts` to Cloudflare — live bundle hash (`index-BIU7HVPh.js`) and byte count (193,808) match the local build exactly, and the live bundle contains the new `payment_method` field. `chickshackg84.com` returns 200 throughout.
- **Same session, Imran confirmed the chime is loud (his exact words: "Yes it was loud. And annoying. Good") — item 4 CONFIRMED working on the real tablet.** Also confirmed already-correct (no code change needed): the new-order chime already fires regardless of which in-app tab (Pending/Active/All) is on screen, on its own independent poll — verified by re-reading `OnlineOrdersPage.tsx`'s `checkForNewOrders` effect and comparing directly against `C:\FBAI\bilal-app\src\worker.js`'s `pollInbound`/`playChime`/`showOSNotification`, same technique. Separately, a real printer incident: printer switched off mid-order, reprint came out truncated — assessed as a printer/RawBT stuck-buffer issue (full power-cycle + fresh order suggested), not caused by tonight's `print_service.py` changes, since that diff only removed text and didn't touch how the payload streams. **Not yet independently confirmed clean on a retest.**
- **New lead, same evening: Imran is referring a second UK restaurant** (wants to avoid Stripe, prefers Bank of Scotland/Lloyds or Clydesdale Bank — name not yet known). Payment-gateway research (Cardnet/Worldpay/Opayo/PayPal/Stripe fees compared) written up in `_context/notes/2026-08-01_uk-payment-gateways-non-stripe.md`; open question is what specifically went wrong with Stripe for this client, not yet answered. Also fixed two Chick-Shack docs that were sitting outside `_context/clients/chick-shack-uk/` and logged the multi-tenant client-folder convention as a standing rule (`memory/multi-tenant-client-folders.md`).

## ✅ OI-57 / OI-58 built AND deployed session P (2026-08-01) — resume here for Malik's UAT only

**Both fully built, curl-verified, and deployed live — see the top of this file and
`_state/open-items.md` for complete detail.** Malik's own words, the bar for calling this closed:
*"no half cooked jobs... once everything is 2000% done only then confirm, i will then do UAT."*
That bar is met and Malik explicitly said "commit and push" before either commit or deploy
happened. **The only thing outstanding is Malik's own UAT — do not re-build either item.**

- **OI-57 — online-orders queue date filter/pagination/sort — ✅ BUILT + DEPLOYED**, commit `55ac6de`.
- **OI-58 — Chick Shack lean branded reports — ✅ BUILT + DEPLOYED**, commit `55ac6de`.
- If picking this up fresh: don't rebuild, don't redeploy. Point Malik at
  `eats.sitaratech.info/online-orders` (date/pagination/sort controls) and its new "Reports" button
  (`/online-orders/reports`) for UAT.

<details><summary>Original ask, kept for reference (both now built per this spec)</summary>

- **OI-57 — online-orders queue: date filter (today-only default, not all-time), pagination
  (`offset`+`total_count`, not just a bare `limit`), and a sort toggle** for Active/All (Pending's
  existing FIFO oldest-first default is deliberate — keep it unless Malik says otherwise on UAT).
  Reproduced the underlying bug already, in the local DB: 7 total online orders exist, all from
  2026-07-28, 5 still sitting unaccepted — Pending shows 3-day-old orders today with nothing to
  scope it to "today." Exact files/line numbers already identified in the OI-57 writeup.
- **OI-58 — Chick Shack reporting: a lean, branded reports view.** Access is NOT the gap (Imran and
  Malik are both already `admin` role and could reach `/admin/reports` today) — the gap is that
  online orders are silently dropped from every existing report/dashboard breakdown despite being
  counted in top-line totals, and the existing reports UI is the wrong shape for a single-channel
  tenant. Fix the online-orders-invisible bug platform-wide first (benefits every future
  online-ordering tenant, not just this one), then build a new lean route with Daily Sales
  (custom range), Prepaid vs Cash-on-Delivery (new), Rejected Orders (new), and a Stripe
  reconciliation report last (Malik flagged it "maybe" — lower priority, build after the other
  three are solid).

</details>

- **Capture-on-accept (OI-41), root cause found.** `create_checkout_session` read `session["payment_intent"]` immediately after `Session.create()` and stored it on the order -- but confirmed against the real sandbox (a throwaway probe session), Stripe does **not** create the PaymentIntent at that point, only once the customer actually submits payment. `orders.stripe_payment_intent_id` was written `None` and stayed that way forever: the webhook's own backstop (`payment_intent.amount_capturable_updated`) never persisted it either, and was itself blocked by an unrelated, prematurely-set `payment_authorized_at`. `accept_order`'s guard on `stripe_payment_intent_id` then silently no-opped on Accept -- no exception, nothing logged, straight through to `in_kitchen` with `payment_status` still `unpaid`. Confirmed against the real order (`260731-001`): DB had `stripe_checkout_session_id` + `payment_authorized_at` set but `stripe_payment_intent_id` still `None`; Stripe's own PaymentIntent (`pi_3TzL3jFnGj7KcDjJ0NYqItbA`) was sitting fully authorised, `requires_capture`, `amount_capturable: 1299` -- the money was never lost, just never captured.
  **Fix (commit `593513b`):** `accept_order` now guards on `stripe_checkout_session_id` (reliably set at session-creation) and resolves the missing intent id from Stripe directly via new `stripe_service.resolve_payment_intent_id`. The webhook independently backfills the id from its own event object. The premature `payment_authorized_at` write at session-creation was removed. **7 new tests, 2 mutation-checked by hand** (temporarily reverted each guard to its old shape, confirmed the new test fails, restored the fix). Full suite: 442 passed, same 12 pre-existing QB-Desktop/parked failures. Deployed and **verified live inside the container** (both the new function and the corrected guard read back from the running backend, not just a green Action).
  **⚠️ H-6 was already actually done**, confirmed directly against the Stripe API this session (webhook registered at `eats.sitaratech.info/api/v1/public/stripe/webhook`, enabled, all 4 events subscribed) -- the line below and the old "H-6 outstanding" language elsewhere in this file were stale.
  **Closed out:** order `260731-001` voided (`pg_dump` backup taken and verified first, 42 tables) and its Stripe authorisation explicitly cancelled -- confirmed directly against the Stripe API afterwards: `status: canceled`, `amount_received: 0`. No money was ever taken. **Imran has not yet re-run the test with a fresh order.**
- **Tablet "new order" sound, root cause found (two bugs), fixed, commit `87923b4`.** (1) The chime only fired `if (which === "pending")` -- a tablet left on the "Active"/"All" tab never rang for anything new, silently. (2) The real cause of total silence: `chime()` built a brand-new `AudioContext` on every poll tick, never from a user gesture. Chrome -- Android especially, which is what this tablet runs -- creates every `AudioContext` `suspended` until resumed inside a genuine tap, with **no exception thrown**, just no sound. The exact same "Chrome on Android needs a real gesture" rule already bit the `rawbt:` print button once before (`ERROR_LOG.md`, 2026-07-29).
  **Fix:** one persistent `AudioContext`, resumed from a new explicit "Enable sound" button (mirrors the KDS's existing audio on/off pattern) that plays an immediate confirmation beep on tap. The new-order watch now polls independently of whichever tab is on screen. `tsc` + `vite build` + eslint all clean; no browser-in-the-loop test possible (Chrome extension still won't connect, consistent with every session this week). **Malik has not yet tapped "Enable sound" or retested live.**
- **Malik/Imran ran the real end-to-end test (order `260731-003`, 2026-08-01). OI-41 itself is PROVEN: verified directly against Stripe (`status: succeeded`, `amount_received` exactly matches the order total, capture landed ~1s before `accepted_at`) and the DB (`payment_status: paid`, intent id correctly resolved this time).** Three separate, real bugs surfaced in that same test, all found, fixed and deployed (commit `b90057c`):
  1. **Printed kitchen ticket said "NOT PAID" despite the order being genuinely captured.** The ticket is a self-contained ESC/POS payload, cached the instant an order enters the pending queue purely so the Print button can navigate synchronously (Chrome drops the `rawbt:` handoff otherwise) -- nothing ever invalidated that cache once payment status actually changed. Fixed: `invalidateTicket` drops the stale entry and re-fetches in the background (never awaited, so it can't reintroduce the dropped-gesture bug) after Accept, Mark paid, and a cash-settled handover.
  2. **Chime was too quiet for a crowded, noisy restaurant floor.** Reused the already noise-tested 3-tone chime + OS Notification pattern from `C:\FBAI\bilal-app\src\worker.js`, pushed louder again per Malik's explicit ask (gain capped just under 1.0 to avoid clipping; the sequence repeats once). The OS notification is a second, independent channel armed in the same "Enable sound" tap.
  3. **Accepted-order email's "Payment: Paid" was plain muted grey**, easy to miss beside "Due on delivery". Now bold in HTML; plain-text reads "PAID".
  `tsc` + `vite build` + eslint clean; backend 443 passed (+1 new test), same 12 pre-existing failures. **Not yet re-verified live by Malik/Imran** -- a second full retest is the next step, not a formality: confirm the ticket now prints PAID, the chime is actually loud enough, and the email reads clearly.
- Also surfaced and explained during this test, not bugs: (a) the storefront's "Notes for the kitchen" box persists per-browser and only clears on a **successfully placed** order, so leftover text from an abandoned earlier test can resurface -- pre-existing, was already flagged unfixed in `-F`, not yet scheduled; (b) the Pay button silently stayed disabled because the test delivery address ("Test", 4 chars) failed a `> 4` length check with zero visible error -- working as designed, but the lack of any inline validation message is a real UX gap worth fixing, not yet done.

**Session M — independent re-verification of the whole photo round, against Malik's own source doc (`Imran Links.docx`), not against our own checkpoints.** Malik queried the count ("31 links"); the docx (30 link-lines: 29 distinct external source photos + 1 self-referencing reuse-instruction link) was cross-checked one-for-one against every row already recorded — full match, nothing skipped, nothing extra. Re-verified live from scratch (not trusting the prior session's claims): live API (87 items, 0 duplicate names, all 10 drink names correct), all 38 image basenames × thumb+hero (76 files) fetched fresh from `chickshackg84.com` and confirmed valid, checkout disclaimer + testing banner confirmed present in the live JS bundle. **Found and fixed one real bug in the PDF-regeneration script itself** (not a live-site bug): compositing a transparent webp onto RGB directly left black/checkerboard artifacts in the "now on site" column; fixed by flattening onto white via the alpha channel first. Regenerated `Chick_Shack_Photo_Review.pdf` (Desktop, not git-tracked) with fresh live thumbnails for all 27 used photos. Still open: Hash Brown's photo mapping remains Claude's own guess, never confirmed by Imran — flagged again in this PDF.

**Session M continued — 4 more of Imran's links wired in and deployed: Gravy (8oz), Coleslaw (8oz), Spicy Rice, Beans (8oz).** All 4 previously had no photo at all (inherited category fallback). Gravy from `rendalls-cdn.co.uk`, Coleslaw and Rice from the already-vetted `chunkychicken.com`, all clean. **Beans caught a real issue**: the source Malik got approval to use was a live `shutterstock.com` preview URL with a visible "shutterstock.com · 83031757" watermark baked into the bottom of the image — Claude initially and wrongly told Malik it had no visible watermark; caught it while reviewing the actual crop, corrected course, re-asked, and on his direction cropped the watermark strip out before deploying (same bowl photo, no credit line live). `tsc` + `vite build` clean for both rounds, deployed via `cd storefront && npm run deploy`, verified live (byte-exact match on all new image URLs, new JS bundle hash confirmed in `index.html`). Commits `2b7f7b0` (gravy/coleslaw/rice) and `bc7076c` (beans), both pushed. `Chick_Shack_Photo_Review.pdf` regenerated with a new "New this round" page; total tracked photo links now 33.

**Session M continued — Salad Box (real photo) + Fruit Shoot (deliberate brand-mismatch override) deployed.** Salad Box: Imran's own kitchen photo of the actual product (WhatsApp), no provenance concern at all — best source of the whole round. **Fruit Shoot: Malik explicitly instructed deploying the "Simply Fruity" bottle photos as the live Fruit Shoot Orange/Blackcurrant photo**, after being shown clearly (in higher resolution than before) that the branding reads "Simply Fruity", not "Fruit Shoot" — same mismatch already rejected twice this session (once via a blurry gstatic thumbnail, once via this same clearer photo when Claude first asked). Both crops legibly show "SIMPLY fruity" branding on the live site — a fully informed decision, not a quality miss. `MenuItem.image` is item-level not per-variant, so one combined photo (both bottles) represents the whole Fruit Shoot line (2 flavour variants). PDF's "NOT USED" section rewritten to note this instead of listing Fruit Shoot as rejected. Commit `7ddb77c`, pushed, verified live (byte-exact). **If Imran or a customer ever asks why the drink shows a different brand name, the answer is on record here** — flag it back to Malik if it comes up, don't silently re-decide it.

**Session L, later rounds (commits `55373da` through `57f6915`):** Continued live photo
sourcing + Imran's UAT feedback. Wired in 22 more real photos total (Boneless Breast, Peri
Burger, Chicken Fillet Burger, Fish/Veggie Burger and Veggie Wrap — previously had NO photo at
all, Chicken Fillet/Peri Wrap, Sides category fallback, Onion Rings, Peri+Plain Wedges, Corn
Cob, Mozzarella Sticks, Hash Brown, and the full drinks set: Irn Bru, Diet Irn Bru, Rubicon
Passionfruit, Levi Roots, Water, Pepsi, Pepsi Max, Fanta Orange, 7up, plus Chilli Cheese Bites).
Two photos deliberately NOT used — "Simply Fruity" bottles sent for Fruit Shoot are a different
brand entirely, same class of mismatch as the Coca-Cola photo rejected in OI-56. Also built:
drink serving-size labels (all soft drinks now "(Can)", Water "(500ml)", Fruit Shoot "(330ml)")
— required a production DB rename (`rename_chick_shack_drinks_2026_07_31.py`, same idempotent
in-place-UPDATE pattern as the earlier item/dip renames this session, `pg_dump` backed up first,
verified live via API: zero duplicates, zero stale old names, 87 items unchanged) — and a
delivery service-fee disclaimer on Checkout's Payment section, matching the printed menu board's
exact wording. Generated `Chick_Shack_Photo_Review.pdf` (local `fpdf2` + Pillow, no external
service) as a client-facing deliverable for Malik to send Imran — one row per photo with source
link, source thumbnail, live-site thumbnail, and status; regenerated after each round. Saved to
`C:\Users\Malik\Desktop\Chick_Shack_Photo_Review.pdf`, NOT git-tracked. Every one of Imran's 29
photo/feedback links sent this session has now been reviewed and either deployed or explicitly
flagged as not used — nothing outstanding. Full ledger in `PAUSE_CHECKPOINT_2026-07-31-D.md`
and `-E`.

**Session L in one line:** Built the per-item kitchen-notes feature Malik asked for right after
approving UAT item (iv) — design confirmed with him first via `AskUserQuestion` (two rounds;
his second answer corrected a too-abstract first framing), then built: a free-text "Anything
else?" field in `ItemModal.tsx` next to the "leave it out" ticks, travelling the same path as
exclusions (`CartLine.note` is part of the line's identity like `exclusions`, joins the line's
`notes` string, prints bold `** ` on the kitchen ticket — zero `print_service.py` changes
needed). Connection to Checkout: `orderNotes` was lifted out of `Checkout.tsx` local state into
the cart store itself, so `add()` can write `"ItemName: note"` straight into the same box the
customer sees at checkout, and it survives navigating back to the menu (Checkout is conditionally
unmounted, not just hidden). Basket persist version bumped 3→4 (same discard-at-boundary
treatment as the exclusions bump). Caught and fixed one real bug before shipping: the new
textarea's `text-sm` class silently overrode `index.css`'s global `textarea { font-size: 16px }`
rule, which exists specifically to stop iOS Safari zooming the page on focus — switched to the
same `.field` class every other input in the app uses. No backend/DB changes at all, so no
`pg_dump` needed — pure frontend, `tsc`+`vite build` clean. Deployed via
`cd storefront && npm run deploy`; first bundle fetch hit the same "mid-propagation SPA
fallback" Cloudflare issue `ERROR_LOG.md` already documented from session J (200 OK, ~1KB of
`index.html` instead of the real ~192KB bundle) — waited 8s, re-fetched, got the real
192,520-byte bundle matching the build output exactly, with the new strings and the testing-mode
banner both confirmed present. Commit `d0d3199`, pushed. Chrome extension tried again this
session (4th session running) — still would not connect; verified structurally + via the live
bundle instead, per the now-established pattern.

**Session K in one line:** Malik's first live UAT pass on OI-45(b) surfaced 3 real issues,
all fixed and deployed: (1) a solo item gave no hint a Meal version existed — Meal items were
appended in one block after every solo item in a category instead of interleaved, and the
item modal had no cross-link; both fixed, plus a `reorder_chick_shack_meal_modifiers_2026_07_31.py`
one-off was needed to fix the *live* modifier-group order too, since `seed_chick_shack.py`'s
`_link()` is additive-only and a plain reseed doesn't reposition an existing link (same failure
shape as the two rename bugs from the session before). (2) Meal items showed optional dip/sauce
choices before the required drink + chips upgrade — reordered. (3) Checkout landed scrolled to
the bottom of the page — `view` swaps screens in place rather than routing, so scroll position
carried over; added scroll-to-top on every view change. Backend: `pg_dump` backed up, reseed +
reorder script run on production, verified via the live API (item order + group order both
correct). Storefront: deployed to Cloudflare, live bundle verified for the new code, testing-mode
banner reconfirmed present. Commit `8017321`, pushed.

**Same session, follow-up:** the modifier-group fix above was too narrow — Malik caught the
identical bug on **solo** items too (Peri Peri Burger showing Dips before the required
Peri-Peri Heat), live. Root cause fixed properly this time in `seed_chick_shack.py` itself:
`_seed_items` now deletes and recreates every item's `menu_item_modifier_groups` links on
every reseed, in the order that item's `modifierGroups` specifies, instead of the old
additive-only `_link()` that never repositioned an existing link. Closes the whole class of
bug for good — any future reorder in menu.ts now takes effect on the next plain reseed, no
one-off script needed. `pg_dump` backed up, reseeded on production, and **swept all 87 live
menu items programmatically**: zero items show an optional group before a required one.
Commit `97ec8c8`, pushed.

**Same session, UAT item (iv):** the "leave it out" ticks (No Onion, No Lettuce, etc.) turned
out to have **never rendered on the live site at all**, for any item. `exclusionsFor()` matched
`item.categoryId` against a hardcoded slug Set ("burgers", "wraps", ...) — correct for the local
fallback menu, but `categoryId` is a database UUID once the live API menu loads, so the check
silently never matched. Same slug-vs-UUID class of bug already solved for images, never applied
here. Fixed by matching on the category's NAME instead (resolved by `MenuBrowser` from its own
always-correct `categories` list, passed to `ItemModal` as a plain prop) — no schema change.
Pure frontend fix, no DB involved. `tsc` clean, deployed to Cloudflare, live bundle verified
for the new code. Commit `a178d78`, pushed. **Malik confirmed fixed, approved.**

## 🔴 Resume here (session L, UAT of Imran's 07-31 six-item list in progress)

**Per-item kitchen notes — BUILT and deployed, live, 2026-07-31 session L.** Design confirmed
with Malik first (see session L summary above). Not yet Malik-verified live (he hasn't clicked
through it yet) — this is a new, unreviewed feature, not one of the original six UAT items, so
flag it to him explicitly rather than folding it silently into the (v)/(vi) walkthrough.



Going one item at a time via `AskUserQuestion`-style manual checks, Malik approving or
reporting back after each. Progress against
`_context/clients/chick-shack-uk/voice-notes/2026-07-31_imran_meal-modifiers-and-photos.md`'s
six items:
- (i) Meal modifiers — ✅ approved, after 3 rounds of real fixes (see above)
- (ii) New-order sound alert — **root cause found and fixed, session N (2026-08-01),
  commit `87923b4`** (tab-scoped chime + unresumed AudioContext, see session N summary
  above). Deployed. Not yet tested live — Malik will tap "Enable sound" and test on the
  real tablet himself.
- (iii) Allergy notice + kitchen notes box — ✅ approved
- (iv) Remove-selections ("leave it out" ticks) — ✅ approved, after fixing a real bug (see above)
- (v) Burger name suffixes — ✅ approved. Pre-checked server-side by sweeping the live production
  API (`GET /public/chick-shack/menu`, all 87 items) before asking Malik to look: all 10 burger
  items end "…Burger", all 6 wrap items end "…Wrap", Meal siblings correctly read "…Burger Meal" /
  "…Wrap Meal", zero duplicate names anywhere — ruling out the stale-duplicate-row failure mode
  `ERROR_LOG.md` documented for this exact rename. Malik then confirmed visually on the live site.
- (vi) Chunky-chicken photos — **in progress** (built and deployed in session I/J, being walked
  through now as part of THIS structured UAT pass)

**Per-item notes ask from Malik right after approving (iv) — ✅ BUILT, deployed, live-tested by
Malik, session L.** Design confirmed via two rounds of `AskUserQuestion` before any code was
written: ticket style = same bold treatment as exclusions; connection = the item note is written
straight into the same Checkout "Notes for the kitchen" box, editable from there. Malik tried it
live and found one real UX issue: the auto-inserted text was prefixed `"ItemName: comment"`,
which reads as clutter with several items each carrying a note. Fixed to insert the plain comment
text only (no item-name prefix) — the per-line note still reaches the kitchen ticket correctly
attached to its own item regardless of what the checkout box says. Redeployed, verified live.
Same session, two more of his live-testing findings, both shipped: the allergen notice was
checkout-only and is now also on the homepage; the Meal-item photos still show the solo item's
photo with no chips/drink in frame — **flagged as needing real photography, not fixed**, since
the only prior candidate photos showing a full meal composition (`menuitem-6.jpg`,
`menuitem-8.jpg` from the session J chunky-chicken source set) were deliberately rejected at the
time for showing a rival Coca-Cola can and a fake competitor-branded box — there is no safe
existing asset to pull from. Malik said to let it wait.

**Same session, direct feedback from Imran (via Malik, WhatsApp screenshots) — three more real
fixes, all shipped and verified:**
1. **Exclusions scoping** — the "leave it out" ticks were showing on Peri Peri Grilled Chicken
   and Fried Chicken too. Imran confirmed directly: only Burgers and Wraps should have it. The
   code already carried a `⚠️` comment flagging this exact scope as an unconfirmed guess from an
   earlier session ("confirm it with him") — now settled by his own words.
   `EXCLUDABLE_CATEGORY_NAMES` cut to `{"Burgers", "Wraps"}`. Pure frontend, deployed, verified
   live (bundle byte count matched build exactly).
2. **Variant visibility** — piece-count options (2pc/3pc/4pc etc.) on fried chicken, wings,
   tenders and peri items were invisible in the menu list; only a "from £X" hinted more than one
   option existed. Added a subtitle to `MenuBrowser.tsx` list cards listing every variant name
   for multi-variant items. Pure frontend, deployed, verified live.
3. **Dip modifier naming** — Imran: kitchen staff need "dip tub" in the wording so a ticket line
   like "- Ketchup" reads as a separate 2oz tub, not an instruction to put it ON the burger/wrap.
   Root cause: `print_service.py` prints a bare `modifier.name` with zero group context, so the
   dip group's own "(2oz tub)" label never reached the kitchen ticket. This one touched the
   database, so handled carefully: `seed_chick_shack.py` matches `Modifier` rows by
   `(tenant, group_id, name)`, so a blind rename in `menu.ts` would have created 9 duplicate
   rows rather than renaming them (the exact additive-only-seeder class already documented for
   item renames). Wrote `rename_chick_shack_dip_modifiers_2026_07_31.py`, same in-place-UPDATE
   pattern as the earlier item-rename script. Sequence: `pg_dump` backup taken and verified
   (88.5KB, 42 tables) → renamed the 9 existing rows in place on production → reseeded → verified
   live via the public API: all 9 dip options now read "…(Dip Tub)", same group id (genuinely
   the same row, not a new group), zero duplicates anywhere across all 87 items, and the 3
   standalone Dips-category products (sold on their own, no ambiguity there) correctly left
   untouched. Also closed in this round: **Imran confirmed printing on his own hardware** — "I
   did print an order yesterday which we received and 3 copies printed" — closing the last open
   piece of OI-51/52.

**Same session, severe regression found and fixed while building item #2 above: every
multi-variant item had silently lost its size/quantity selector, live.** While verifying why the
new variant-visibility subtitle had nothing to show for "Fried Chicken", the live API confirmed
the item had NO Choice modifier group at all, despite `menu.ts` and `chick_shack_menu.json` both
having one. Root cause: `97ec8c8` (earlier today, session K) made `_seed_items` delete and
recreate every item's `menu_item_modifier_groups` links from `entry["modifierGroups"]` to fix
group ORDER — but a multi-variant item's "<name> -- Choice" group is linked separately, and that
delete step ran unconditionally, wiping the Choice-group link out again before session K's own
reseed finished, with nothing in the recreate list to restore it. **Every multi-variant item on
the live site — Half/Full Chicken on the Bone, Boneless Breast 2pc/4pc, Peri Wings, Peri Tenders,
Fried Chicken, Fried Chicken Combo, Spicy Fried Wings, Fried Tenders, and all their Meal
versions — showed only its cheapest price with zero way to select size, piece-count, or
rice/chips/half-half**, silently, no error anywhere (`menuAdapter.ts`'s own documented
flat-price fallback absorbed it cleanly). Fixed by building one `group_ids` list (variant group +
`entry["modifierGroups"]`) and doing a single delete+recreate pass; removed the now-dead
`_link()` helper. `pg_dump` backed up (88.6KB, 42 tables), deployed, reseeded, verified live via
the API: all 16 affected items now correctly expose their full option list, zero duplicates.
Independent confirmation: Imran sent a voice note (transcribed locally with `faster-whisper`,
since it isn't directly playable) describing this exact same missing-selector problem, item by
item, unprompted — everything he listed matched what the fix restored, so no separate feature
work was needed for that note. Malik explicitly declined a check of whether any real customer
order was placed during the broken window ("forget the existing orders, just fix and deploy").

**Same session, 3 stock photos replaced with real photography, Imran-supplied reference links.**
Two from `chunkychicken.com` (confirmed same UK "Chunky Chicken" franchise brand as the OI-56
source, `chunky-chicken.uk` — not a different, unvetted business): grilled chicken quarters now
the **Peri Peri Grilled Chicken category fallback** (`peri-grilled.webp`, was still original
stock), and grilled wings now the **Peri Peri Wings** item photo (`peri-wings.webp`, also still
original stock). A third link was a Google Images thumbnail-cache URL (`gstatic.com`) with no
identifiable original source — flagged to Malik as the same class of unclear-provenance risk
already rejected once in OI-56 (the Coca-Cola can, the fake-branded box); **Malik explicitly
overrode that caution** ("just add the picture its fine") and it was used as a new **Peri
Tenders** per-item photo (previously had none, inherited the category image) — grilled tender
strips with chips, added as a new `ImageName` entry. All three sources had genuine alpha
transparency (verified with PIL before cropping), so none needed the white-patch fix the nuggets
photo required. Cropped to thumb (240×180) and hero (720×480) separately per the established
convention, deployed, and verified live — all 6 image URLs return the correct byte-exact files
(one `peri-tenders` URL hit the known Cloudflare mid-propagation SPA-fallback issue on first
check, resolved after a longer wait and confirmed on retry).

**Next action:** UAT item (vi), chunky-chicken photos — in progress now.

**Session J in one line:** Finished the photo-integration work session I left in progress
(`PAUSE_CHECKPOINT_2026-07-31.md`). Re-verified every proposed photo→item mapping in
`CLASSIFICATION.md` against real `menu.ts` descriptions before wiring anything in — rejected
6 of the 15 approved photos rather than force a bad fit, including two the first-pass
classification missed: a real Coca-Cola can in frame, and a third-party-branded "Chicken" box
with its own logo. 9 photos used (4 swapped in place, 5 new per-item overrides), each cropped
separately to thumb/hero sizes via ffmpeg. Deployed to Cloudflare and verified against the
**live** site (bundle + all 18 image URLs), not the deploy log — caught and confirmed-resolved
one transient bad response on first check. Full write-up: `_state/open-items.md` **OI-56**.
Commit `a361fc8`, pushed.

**Session H in one line:** Added a persistent "under testing, please call instead" banner to
every storefront view (commit `abea022`) — UAT with Imran hasn't happened yet and Stripe/menu
are still being tuned, but the site keeps taking real orders 24/7 in the meantime. Shipped via
`git push` first, which only deploys the POS/backend side; the storefront needed its own
`cd storefront && npm run deploy` (Cloudflare Workers), run and verified separately by fetching
the live bundle. **`docs/DEPLOYMENT_PLAYBOOK.md`'s one-line summary was rewritten** to state
both pipelines up front — see `ERROR_LOG.md` 2026-07-30 session H for the full incident. Banner
stays until Malik says to remove it; it is copy-only, does not disable checkout.

**Session G in one line:** OI-55 fully closed (Brevo authenticated + proved + branded HTML
shipped at `3ab141b`, deployed, verified live). Card payment (OI-41/H-6) investigated and
explained — not a bug, deliberately flagged off — but deferred: proving capture-on-accept
needs the shop genuinely open and someone accepting a real order, so Malik is resuming that
**next time the restaurant is open** (storefront itself shows "Opens 16:00" same day,
2026-07-30 — Malik said "tomorrow," so confirm which he means before assuming either).
**Loose end: order `260730-001` ("Chicken Fillet", placed to prove the HTML email) is a real
pre-order still sitting in the queue**, same situation as the two from earlier in the
session — nobody voided it. Give Imran a heads-up or void it via `reject_order` before he
opens, same pattern used twice already this session.
✅ Session E ended fully pushed and deployed at `7797af2` (the "held back Stripe commits" in an
earlier header version were pushed late in session E; Stripe live in **TEST mode**, keys verified
in the container). **Session F adds 4 commits — OI-51…OI-54 — and pushing them IS the deploy.**
That deploy runs migration `q3r4s5t6u7v8` (additive column on `restaurant_configs` + chick-shack
backfill by slug). Verify the effect after push per the playbook: deployed commit, schema
revision `q3r4s5t6u7v8` inside the backend container, every hostname's own certificate.

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

*~~Email still sends nothing: no SMTP provider and no sending domain chosen.~~ **Superseded
2026-07-29 session D** — Mailjet is wired, DKIM verified, 9 keys live in the running container,
`orders@chickshackg84.com` sends and receives. OI-43 is RESOLVED. **No real message has been sent
yet**; the UAT is the first one.*
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
| Chick Shack storefront | ✅ **Live** on the client's real domain, Cloudflare SSL. 🟡 **Testing-mode banner up on every view since 2026-07-31** ("please do not place an order, call 07719 566 889 instead") — checkout itself is unchanged and still works, this is copy-only. Stays until Malik says remove it | `_state/chick-shack-uk.md` |
| Chick Shack ordering | 🔴 **LIVE, 24/7.** Out-of-hours orders are accepted as **pre-orders** and shown as such on all three surfaces. Accept/reject is always manual | `_state/chick-shack-uk.md` |
| Chick Shack tenant + menu in DB | ✅ **Seeded locally and on production 2026-07-28/29** — 8 categories, 62 items, 11 delivery areas, GBP. Logins verified | `_state/decisions.md` D-11 |
| Multi-tenant routing | ✅ **Fixed 2026-07-28.** Public routes keyed by slug; PIN login no longer searches across tenants | `_state/decisions.md` D-10 |
| Public ordering API | ✅ Built, tenant-scoped, queue endpoint. **Deployed 2026-07-29** | `_state/chick-shack-uk.md` |
| Order-queue tablet view | ✅ **Deployed with the full lifecycle** at `/online-orders`. Accept → out for delivery → delivered/paid; completed orders leave Active. **Not yet opened on Imran's real tablet** | `_state/open-items.md` OI-36 |
| Storefront checkout wiring | ✅ **Merged and PUBLISHED 2026-07-29.** Menu from the API, checkout posts, confirmation follows the order to delivered. Email required; "leave it out" ticks print on the ticket | `_state/open-items.md` OI-28 / OI-37 |
| API access from the storefront domain | ✅ **Fixed on the server 2026-07-29.** `CORS_ORIGINS` now allows both Chick Shack origins; preflight verified, unknown origins still refused | `_state/open-items.md` OI-40 |
| Stripe | ✅ **LIVE MODE, proven with a real transaction, 2026-08-02 — as of now (source: Malik + Imran verbal/WhatsApp, cross-checked against our own DB same session).** Order `260801-004`, £2.78, Imran's real card, captured for real — confirmed against Stripe's live dashboard, our `payments` table, and the audit trail. Live keys set directly on the server by Malik (never passed through the assistant). **Imran approved going fully live in writing.** `cardPaymentEnabled` is **still false as of this row** — flipping it, removing the testing banner, and shipping a new delivery cut-off feature are in progress this same session, not yet deployed; see the session Q "Resume here" section above for exact status. **Test override still exists:** `chickshackg84.com/?card=1`. H-1 through H-10 previously all confirmed done | `docs/STRIPE_HARDENING_CHECKLIST.md` · OI-20 / OI-41 |
| Printing | ✅ **ON PAPER (photographed 2026-07-29)**, session F built Imran's two asks: **3 labelled copies per ticket in ONE payload** (one `rawbt:` navigation) and the **daily `#NNN` double-size at the top of each copy**. **Paper check on his own printer now CONFIRMED 2026-07-31 (session L)** — Imran, to Malik: "I did print an order yesterday which we received and 3 copies printed." Closes the last open item under OI-51/52 | OI-51 / OI-52 ✅ built + ✅ confirmed on real hardware · `ERROR_LOG.md` |
| Served / delivered gap | ✅ **CLOSED and deployed.** Tablet has out-for-delivery / delivered / mark-paid; completed orders leave the Active tab; the customer's page follows it | `_state/open-items.md` OI-44 |
| Customer emails | ✅ **RESOLVED 2026-07-30 — Brevo live, real order proved it, then branded.** Order `260729-003`: confirmation delivered in 2 seconds, Gmail "Show original" — SPF PASS, DKIM PASS (`d=chickshackg84.com`), DMARC PASS. Domain authentication needed a fix along the way (Brevo requires its own DMARC record to flip `authenticated`; resolved by editing Imran's single `_dmarc` record in place, same `p=none` policy, not duplicating it). **Same session: all 4 emails (received/accepted/rejected/on_the_way) given branded HTML** — ink/flame/ember from `tailwind.config.js`, no logo (none exists), inline-style table layout for client compat, every customer-supplied string `html.escape()`'d (checkout form is public input). Shipped `3ab141b`, deployed, verified live via order `260730-001` — real Gmail screenshot confirms it renders as designed. Test suite: 45/45 email tests, 432/444 full suite (12 pre-existing, unrelated). Runbook: `_context/clients/chick-shack-uk/EMAIL_SETUP_RUNBOOK.md` | `_state/open-items.md` **OI-55** |
| Menu modifier prompts | ✅ **BUILT and deployed to production, 2026-07-31.** Peri-Peri Heat renamed to match his till; "make it a meal" is now 25 real Meal sibling products (drink + chips upgrade), not a flat +£3 tick. Exclusion ticks (no lettuce etc.) turned out to already be built. Verified against the live API: 87 items, no duplicates | `_state/open-items.md` OI-45 |
| Storefront photos | ✅ **12 real photos live now** (9 from OI-56 + 3 more session L, same-day): Peri Grilled category fallback, Peri Wings, and a new Peri Tenders photo. 6 of the original 15 rejected on re-verification (2 trademark, 4 product mismatch). Only **fried-chicken, fried-tenders, sides-chips** still on original stock. Meal-item "with chips & drink" composite photos still needed — flagged, deferred, no safe asset exists | `_state/open-items.md` OI-56 |
| Backend test suite | ✅ **409 passing — run and verified 2026-07-29 session E**, not inherited. Session E started from a verified **393** (session D's "391" was two short) and added **16** for the Stripe hardening. Same **12 pre-existing failures** throughout (10 failed + 2 errors), all in QuickBooks-Desktop/parked code | `ERROR_LOG.md` |
| Core POS (10 phases) | ✅ Production, 98/99 UAT | `_state/pos-platform.md` |
| QuickBooks Online | ✅ Live. Sync is **manual by design**, not broken | `_state/pos-platform.md` |
| POS demo sites | ✅ Green (`pos-demo.duckdns.org`, `eats.sitaratech.info`) | `_state/infrastructure.md` |
| CI (`ci.yml`) | ❌ **Red on every commit.** Ruff + ESLint fail; Ruff exits before the test step, so **CI has never run the suite**. All findings are in parked code, none are live bugs. Deploys are a separate workflow and are green | `_state/open-items.md` OI-47 |
| Nightly demo-data cron | ❌ **Has never run** | `_state/open-items.md` OI-11 |
| Production log persistence | 🟡 **Backend fix designed and written, PAUSED uncommitted, session Q (2026-08-02).** `backend`/`nginx` are recreated on every deploy and are `read_only:true` with no persistent volume, so `docker logs` history is lost every push — sometimes within hours. All 6 backend files edited/written, config validated directly, but not build-tested, not committed, not deployed — resume from OI-60a's checklist, don't redesign. nginx not started | `_state/open-items.md` **OI-60** |

---

## 🔴 Next action — set by Imran's live walkthrough, 2026-07-29 (session E)

**Session F built all four walkthrough items** — details in `_state/open-items.md`:

1. ✅ **OI-51** — three copies per ticket, repeated **inside** the ESC/POS payload.
2. ✅ **OI-52** — daily `#NNN` double-size + "COPY n OF 3" on every copy. No new counter.
3. ✅ **OI-53** — `/orders` shows Accept (routes to the queue) and trims online orders;
   the server now **refuses** the generic `confirmed→in_kitchen` for online orders, which
   would have cooked food without ETA, capture or notification.
4. ✅ **OI-54** — `online_ordering_only` per-tenant flag; chick-shack lands on
   `/online-orders`. Migration backfills production by slug, so the deploy flips it.

Still to verify on the real tablet/printer: 3 slips with big numbers actually on paper.

5. ✅ **OI-55, email egress — DONE 2026-07-30.** Brevo authenticated, `BREVO_API_KEY` live
   on the server, real order `260729-003` delivered its confirmation email in 2 seconds with
   SPF/DKIM/DMARC all PASS. **Same session, also shipped:** branded HTML for all 4 emails
   (`3ab141b`), verified live via order `260730-001`. Closed.

## 🔴 Resume here (session G paused 2026-07-30 ~06:15 PKT)

1. **Void or flag order `260730-001`** before Imran opens — see note at the top of this file.
2. **Stripe card payment, next time the shop is open:** use `chickshackg84.com/?card=1` to
   reveal the card button (hidden from real customers on purpose), run a real TEST-mode card
   through checkout, then **accept the order on the tablet and confirm the capture actually
   fires** — that's OI-41, and it can only be proven with the shop live because capture is
   tied to a real Accept action, not to checkout.
3. **H-6** (dashboard-only, can be done anytime, doesn't need the shop open): register the
   webhook in the Stripe dashboard, then put `STRIPE_WEBHOOK_SECRET` on the server. Code side
   already done — see the checklist under H-6.
4. Once OI-41 + H-6 both close, flip `cardPaymentEnabled: true` in `storefront/src/data/menu.ts`
   and redeploy — that's what actually turns the card button on for real customers.

*Everything below this line predates the walkthrough.*

## Next action

**Everything up to `447847a` is deployed and published.** `merge to main` is a complete deploy: it
recreates nginx itself and verifies every hostname's certificate, so there is no hand-fixing step.

🔴 **UAT is live NOW.** `chickshackg84.com` accepts orders at any hour and every one lands on
Imran's tablet at `https://eats.sitaratech.info/online-orders?shop=chick-shack`.

In order:

1. **The UAT with Imran** — order → **first real email send** → tablet → print → accept →
   out for delivery → delivered. He has never opened the tablet page on the real device
   (OI-36); that is still the single biggest untested link.
2. **Push the 4 held Stripe commits** once the UAT passes, and watch the deploy — it runs
   migration `p2q3r4s5t6u7`. Verify the *effect* (schema revision, container start time,
   deployed commit), never the exit code.
3. ✅ **Stripe hardening — DONE in session E except H-6.** H-1 to H-5 and H-7 to H-10 are
   fixed, tested and, for the four money-critical ones, **mutation-checked**. H-1 turned out
   to be safe today purely by luck and is now robust; see `ERROR_LOG.md`.
4. ⏳ **H-6, the only hardening item left, and it is a dashboard step for Malik:** register
   the webhook in Stripe, then put `STRIPE_WEBHOOK_SECRET` on the server. The **code half is
   already done** — all six Stripe keys are now declared in `docker-compose.demo.yml`, which
   they were **not** before (they would have been written to the env file and never reached
   the container: card silently off, deploy green). Exact steps are in the checklist under
   H-6.
5. **Storefront card UI** — `cardPaymentEnabled` stays `false` until a test card completes end
   to end (OI-41).
6. **OI-45 menu modifiers** (fully specified, no schema change) and **OI-48 time picker** (new,
   not built, not a tweak).

**Client answers now in hand:** not VAT registered (OI-38 closed, 0% tax is correct); charge on
acceptance (OI-46 dissolved); Stripe account live with a Developer seat (OI-20 closed); wants a
customer-chosen time (OI-48 raised).

---

## Read before you touch anything

| If you are… | Read |
|---|---|
| Working on the client build | `_state/chick-shack-uk.md` |
| **About to deploy anything** | `docs/DEPLOYMENT_PLAYBOOK.md` — **two separate pipelines.** `git push origin main` ships the POS backend/admin only; the Chick Shack **storefront** needs its own `cd storefront && npm run deploy` (Cloudflare Workers). A green push/Action proves nothing about the storefront — verify the live bundle. See `ERROR_LOG.md` 2026-07-30 session H |
| Touching a server, domain or DNS | `_state/infrastructure.md` **and** `memory/server-deployment-rules.md` |
| Touching the database | `memory/data-integrity.md` — **`pg_dump` first, no exceptions** |
| Debugging something odd | `ERROR_LOG.md` — it is a real log of real mistakes |
| About to re-argue a decision | `_state/decisions.md` — it may already be settled and logged |
| Picking up work | `_state/open-items.md` |

**Standing cautions.** The DigitalOcean box is **shared** with two other projects behind one nginx —
`docker ps -a` and check volume mounts before any container operation. `chickshackg84.com` carries
the client's **live email**; only ever touch its `A` and `www` records. Never echo a credential.
