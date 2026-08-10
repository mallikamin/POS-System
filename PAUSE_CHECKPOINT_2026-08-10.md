# Pause Checkpoint — 2026-08-10

## Project
- **Name**: Restaurant POS (Chick Shack UK online ordering)
- **Path**: `C:\Users\Malik\desktop\pos-project`
- **Branch**: `main`, HEAD `abf6177`, **nothing unpushed**, 124 files dirty (long-standing doc
  reorg plus OI-60's paused backend work — see the warning below)

## Goal

Decode Imran's QR codes, then build and ship a Google review request email for every online order.
**Done and confirmed live by Malik.** The session ends with a new request that has been captured but
not started: Imran wants exact delivery locations and proposes what3words (OI-76).

## Completed

- [x] **Decoded both QR codes** Imran sent. The red one is `https://www.chickshackg84.com/` (the
      menu), the black one is the Google review link `https://g.page/r/Ccxrn-XKIKecEBI/review`.
      Both verified working, including the CORS check that mattered: `www.` is a *different origin*
      from the apex, and it is correctly allow-listed, so the QR does not open a page that renders
      but cannot load the menu.
- [x] **Review request email built, deployed and switched on** (`5dda69f`, `2795ca2`, `52b1d1f`).
      3 hours after the shop accepts, sent only 09:00-22:00 shop-local, items as text, greeting by
      first name. Rejected orders and abandoned card checkouts never get one.
- [x] **Fixed a real bug that shipped in `5dda69f`** — see "Errors" below.
- [x] **Two real emails sent and confirmed by Malik** ("yes both emails fired accurately"),
      `260809-D001` and `260809-D002`, with him on Bcc at his request.
- [x] **Proved the background timer actually runs**, which nothing else could show.
- [x] **Transcribed Imran's 2026-08-10 01:56 voice note** locally with faster-whisper and registered
      it as **OI-76**.
- [x] Diagnosed Malik's "PAID · CASH on a cash order" question: **not a bug**, the cash was collected
      at handover. Left unchanged.

## In Progress

- [ ] **Nothing is mid-build. No file is half-edited.** All work is committed and pushed.

## Pending

- [ ] **OI-76 — the actual next task.** Discuss the options with Malik, then reply to Imran.
      **He asked for advice, not a build** ("I don't know if you think this is a good idea"). Full
      transcript and analysis:
      `_context/clients/chick-shack-uk/voice-notes/2026-08-10_imran_what3words.md`.
      **Nothing is researched yet and nothing may be quoted from memory** — what3words is a
      commercial product and its licensing must be checked against current published terms. The free
      option Imran has not considered is capturing the customer's device GPS at checkout and
      attaching a maps link to the order.
- [ ] **Watch tonight's service.** It is the first fully automatic run of the review email.
- [ ] **OI-74** — hardcoded `Rs.`/`(PKR)` on the QB sync tab and several admin input forms. Noted,
      not fixed, not asked for.
- [ ] **OI-72** — Meta ads, blocked on Imran's durable advertising restriction, and the storefront
      still has no measurement of any kind.
- [ ] **OI-60** — backend log persistence, still paused and uncommitted.
- [ ] Optional: an admin Settings field for `google_review_url` (today it is a SQL update).
- [ ] Optional: the review defect found while tracing the cash question — `isPaid()` treats
      `refunded` as paid, in both `OnlineOrdersPage.tsx:97` and `print_service.py:238`, so a refunded
      order renders a green PAID badge. **Reachable in code; not verified whether the Chick Shack
      tablet can trigger a refund at all.**

## Key Decisions

- **Fire on a timer, not on a staff "Complete" tap** (Malik's call). Staff behaviour cannot decide
  whether the email goes.
- **Anchor on `accepted_at`, not `created_at`.** A pre-order placed at 14:00 is not accepted until
  16:00, and the food only exists after acceptance.
- **`google_review_url` is per tenant and is also the feature switch.** Hardcoding Chick Shack's link
  in the shared email service would be OI-73's hardcoded `(PKR)` in a new costume.
- **The claim is a conditional UPDATE, not a read-then-write**, because `--workers 4`.
- **Claim committed BEFORE sending.** Dying in between costs one review request; the other order
  would re-mail everyone.
- **The storefront confirmation-screen version was dropped.** Malik established the page polls at
  most 2h past acceptance and has no route back once closed, so almost nobody would see it.
- **No photo in the email**, Malik's call. The POS has no food photography (`image_url` is null on
  all 87 live items) and the photos exist only in the storefront, matched by name.
- **Bcc was for two emails only**, and there is nothing to switch off: `notify_customer` has no
  `bcc` parameter, so the automatic path structurally cannot copy anyone.

## Files Modified (all committed and pushed)

- `backend/alembic/versions/t6u7v8w9x0y1_review_request_email.py` — new; two columns plus a partial
  index.
- `backend/app/models/order.py` — `review_email_sent_at` (the claim).
- `backend/app/models/restaurant_config.py` — `google_review_url` (per tenant, also the switch).
- `backend/app/services/email_service.py` — `_body_review`, `_html_review`, `_first_name`, Bcc
  through both transports.
- `backend/app/services/public_order_service.py` — `send_due_review_emails()` and its constants.
- `backend/app/services/review_email_worker.py` — new; the 15-minute timer.
- `backend/app/main.py` — starts and cancels the worker.
- `backend/tests/test_review_emails.py` — new; 25 tests.
- `backend/tests/test_order_lifecycle_and_email.py` — stub updated for the new signature.
- `STATE.md`, `_state/open-items.md`,
  `_context/clients/chick-shack-uk/voice-notes/2026-08-10_imran_what3words.md`.

## Uncommitted Changes

**All of this session's work is committed and pushed.** The 124 dirty files are pre-existing and were
deliberately left alone.

> ⚠️ **Do not `git add -A` here.** The tree still carries OI-60's paused, **never build-tested**
> backend work (`backend/Dockerfile`, `backend/scripts/start.sh`), which would go to production
> untested and can break backend startup. **Stage by explicit filename**, as every commit today did.

## Errors & Resolutions

- **The review email silently binned every peak-dinner order** → fixed in `2795ca2`. The 12h
  staleness cutoff and the 09:00-22:00 window left a dead zone: an order accepted after ~19:00 fell
  due after the window shut, waited for 09:00, and by then had aged out. Raised to 18h. **Caught by
  dry-running the real query against production at switch-on, not by the green deploy.** The bug
  lived in the gap between two passing tests.
- **Adding the `bcc` parameter broke 4 tests in `test_order_lifecycle_and_email.py`** → stub took the
  old 4-argument signature. Fixed. Only surfaced because the whole suite was run, not just the new
  file.
- **My own grep pattern tripped `cred-guard` twice** → rewrote to report counts only, and dropped a
  reference to the mail provider's key name. Do not try to evade that guard; rephrase.
- **`TZ=Europe/London date` reported GMT in August** → git-bash lacks BST tzdata. Get shop-local time
  from inside the container with `zoneinfo`, never from the host shell.
- **faster-whisper CUDA failed with `cublas64_12.dll` not found** → and it fails at *encode* time,
  after the constructor has happily returned, so a try/except around the constructor catches
  nothing. Use `device="cpu", compute_type="int8"`.
- **A production probe "failed" and the failure was correct** → it picked `demo-restaurant`
  (Asia/Karachi) at 01:47 local, so the send window refused. **This feature cannot be probed at an
  arbitrary hour without checking the tenant's local time first.**

## Critical Context

- **Live state: `chick-shack` review email ON, `cosa-nostra` and `demo-restaurant` OFF.** Server at
  `abf6177`, migration `t6u7v8w9x0y1`, all 8 containers healthy, Orbit CRM untouched, 0 backend
  errors, 0 nginx 5xx, all public URLs 200.
- **The worker is unobservable from logs.** App-level `logger.info` never reaches the container log
  (that is OI-60's gap) and there is no `pg_stat_statements`. To prove the timer runs, arm a probe
  order on a tenant whose **local** time is inside 09:00-22:00, with a **whitespace** email address:
  it passes the sweep's `!= ''` filter so it gets claimed, but `send_order_email` strips it and never
  contacts the mail provider. Then delete the probe.
- **`review_email_sent_at` on `orders` is the audit trail.** Populated means asked, NULL means not.
- **Two unrelated deploy pipelines.** `git push` ships the backend and tablet. The storefront needs
  `cd storefront && npm run deploy` to Cloudflare. A green Action proves nothing about the other.
- **Docker Desktop was started during this session** and the local dev DB was migrated to
  `t6u7v8w9x0y1`.
- Production backup taken before the switch-on:
  `~/backups/pre_review_email_20260810_053643.dump` on the server.
- Artifacts published: review copy mockup `077c3104-d28b-4a41-969d-5bcfd52ad241`, and the
  before-sending email preview `82863eb1-7b39-4375-b061-2d1516387e5d`.
