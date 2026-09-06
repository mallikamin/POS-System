# FZ LLC (UAE) — client index

Contact: Martin Zubeldia. Tenant `martin-fz` on https://eats.sitaratech.info.
Two locations: Production & Wholesale, and a delivery-only kitchen. No dine-in.
Commercials: AED 360/month plus AED 1,500 one-time, proposal sent 2026-08-29.

Everything for this client lives in this folder. Nothing about FZ LLC belongs in another
client's folder or only in the repo root.

## What is where

| File | What it holds |
|---|---|
| `discovery.md` | The original requirements conversation |
| `plan-and-todo_2026-08-26.md` | The build plan |
| `feedback_2026-09-02_martin-round1.md` | Round 1, items M1-M7, verbatim and the build write-up |
| `feedback_2026-09-04_martin-round2.md` | Round 2, item M8, two units and a conversion |
| `feedback_2026-09-06_martin-round3.md` | Round 3, items M9-M13 |
| `UAT_FZ_LLC_2026-09-04.md` | UAT script for rounds 1 and 2 |
| `UAT_FZ_LLC_2026-09-06.md` | UAT script for round 3, 43 steps |
| `UAT_RESULTS_2026-09-06.md` | **What was actually seen**, step by step, with screenshots named |
| `API_VERIFICATION_2026-09-06.md` | The API-layer check of all twelve asks. Carries one retraction |
| `ERROR_LOG_FZ.md` | **Every fault found on this tenant**, its cause and its fix |
| `integrations/` | Integration notes for this client |

## Files that are not in git

Screenshots and the client-facing report live in `_files/2026-09-06/uat-round3/`, which this
repo gitignores by convention:

* `UAT_FZ_LLC_2026-09-06.pdf` — the report sent to Martin on 2026-09-06
* `UAT_FZ_LLC_2026-09-06.html` and `build_report.py` — the source it is built from, so it can be
  rebuilt rather than hand-edited
* 89 screenshots, named by the step that produced them

## Standing facts

* His aggregators are sales channels with commission, not order types.
* Sales channels on the tenant: B2B Wholesale, Careem Now, KEETA, Website (card), WhatsApp /
  Direct, noon Food, Deliveroo. **KEETA carries the code `talabat`** and a code cannot be changed.
* Commission rates are entered and real. Do not repeat the retracted "all 0%" claim.
* Expense invoices are stored in the database, tenant-scoped, and served only to a signed-in
  admin or manager. There is no accountant role and no bulk export yet.
* Two commercial follow-ups are open: a demo for his partners, and their preference for a meeting
  at the Dubai office rather than a call.
