# Email setup runbook — `orders@chickshackg84.com`

**Status 2026-07-29 (session F): provider is now BREVO. The code half is DONE and
deployed disabled; what remains is your half — account, DNS, one key on the server.**

**Why the change:** the first real send failed with `TimeoutError` during Imran's
walkthrough. Measured **from the droplet** (session E): outbound SMTP **25/465/587 time
out** (DigitalOcean's standard anti-spam block), **2525 resets**, and **`api.mailjet.com:443`
TLS-resets** — as do `api.eu.mailjet.com` and `api.us.mailjet.com` (session F) — while
Stripe and GitHub handshake fine from the same box. The Mailjet credentials were verified
from the laptop, which proved nothing about the server's egress. **Do not re-test SMTP
ports; that question is settled.**

`api.brevo.com` **handshakes fine from the droplet** — measured 2026-07-29, not assumed.
The backend now sends through Brevo's HTTPS API whenever `BREVO_API_KEY` is set
(`email_service._send_via_brevo`, contract pinned by strict-fake tests and a mutation
check). The SMTP path remains in the code for a future host whose egress permits mail.

The old Mailjet account, its two DNS records and the 9 `SMTP_*`/Mailjet keys on the server
are **harmless and can stay** — with `BREVO_API_KEY` set, the API path wins (tested).
Remove them later at leisure, never as part of this change.

**Send-path proof carried over from session D:** all four messages (`received`, `accepted`,
`rejected`, `on_the_way`) build correctly with `From: Chick Shack <orders@chickshackg84.com>`,
a distinct `Reply-To`, the order number in the subject and the `£` intact; and the guards
hold — no address → no send, unknown event → `False`, unconfigured → `False`, a **dead
provider is swallowed** rather than failing the order (re-tested for the Brevo transport,
including a refused key and a connection reset).

---

## The one thing that makes this safe

`chickshackg84.com` carries **Imran's live business email**. On 2026-07-27 a Cloudflare
auto-import silently dropped all four of its DKIM records — nothing alerts you when that
happens, mail just quietly degrades.

**Baseline (re-verified against 1.1.1.1 on 2026-07-29, session D). This is the exact record
set to diff against after any DNS change — do not diff from memory:**

| Record | Current value | Touch it? |
|---|---|---|
| MX | `mailserver.livemail.co.uk` (pref 10) | ❌ **NEVER** |
| SPF (TXT) | `v=spf1 mx a include:_spf.livemail.co.uk ~all` | ❌ **NEVER** (see below) |
| DMARC | `v=DMARC1; p=none;` | ❌ leave — it already satisfies any "DMARC required" check |
| DKIM `livemail1._domainkey` | CNAME → `livemail1._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |
| DKIM `livemail2._domainkey` | CNAME → `livemail2._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |
| DKIM `livemail3._domainkey` | CNAME → `livemail3._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |
| DKIM `livemail4._domainkey` | CNAME → `livemail4._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |
| TXT `mailjet._*` (2 records, session D) | Mailjet ownership + DKIM | leave for now — harmless |

**Everything we add is a NEW hostname. Nothing existing is modified.**

### If Brevo's wizard tells you to edit SPF — don't

Same reasoning as before: a domain may have only **one** SPF record, so any provider's
"add our include" instruction means *editing* the live record that protects his business
mail — the single change that could damage it. It buys nothing: **DMARC passes if SPF *or*
DKIM aligns.** Brevo's DKIM will carry the domain, so DMARC passes on DKIM alone. If the
wizard shows SPF as incomplete, that is expected and acceptable.

---

## Step 1 — Brevo account (you)

1. Sign up at <https://www.brevo.com/> — free plan, no card. **300 emails/day**, which at
   ~3–4 emails per order is ~75+ orders/day, well beyond launch volume.
   (Resend's 3,000/**month** was rejected as too tight for exactly this reason.)
2. **Settings → Senders, Domains & Dedicated IPs → Domains → Add a domain** →
   `chickshackg84.com`, and choose to **authenticate the domain yourself / via DNS**.
3. Brevo shows the records to add — a verification code record plus DKIM records.
   **Use the exact names and values from that screen** (they are per-account; this runbook
   deliberately does not guess them).
4. **Settings → SMTP & API → API Keys → Generate a new API key.** Name it `pos-backend`.
   **Do not paste it into chat.** It goes straight onto the server (Step 4).

## Step 2 — DNS in Cloudflare (you)

Add **exactly the records Brevo's wizard shows, and nothing else** — they are all on
**new** hostnames, so nothing existing is modified. Rules that always apply:

- **TXT/CNAME records only on new names** (the verification code and `*._domainkey.*`
  names Brevo gives). If any instruction would *edit* MX, SPF, DMARC or a `livemail*`
  record — **stop, skip that instruction** (see the SPF note above; DMARC already exists).
- Enter the **name part only** — Cloudflare appends the zone. `mail._domainkey`, **not**
  `mail._domainkey.chickshackg84.com`, or you create a doubled name.
- **DNS only — never the orange proxy cloud** on these records.

Then click **Verify / Authenticate** in Brevo.

## Step 3 — Verify DNS before going further (either of us)

```bash
# The records you just added must resolve (use the exact names from Brevo's screen), e.g.:
nslookup -type=TXT <brevo-verification-name>.chickshackg84.com 1.1.1.1
nslookup -type=TXT mail._domainkey.chickshackg84.com 1.1.1.1   # or CNAME, as given

# NOTHING BELOW MAY HAVE CHANGED. Run it and compare to the table above.
nslookup -type=MX  chickshackg84.com 1.1.1.1
nslookup -type=TXT chickshackg84.com 1.1.1.1
for s in livemail1 livemail2 livemail3 livemail4; do
  nslookup -type=CNAME $s._domainkey.chickshackg84.com 1.1.1.1
done
```

**If MX, SPF or any of the four `livemail*` selectors changed, stop and restore before
sending anything.** Verify the records you did *not* intend to touch, not just the ones
you added — that is the 2026-07-27 lesson.

## Step 4 — Server env (me, or you)

One key. On `159.65.158.26`, in `~/pos-system`, **back up the production env file first**
(timestamped copy, same as every other change), then append:

```
BREVO_API_KEY=<the key from Step 1.4>
```

`EMAIL_FROM=orders@chickshackg84.com`, `EMAIL_FROM_NAME` and `EMAIL_REPLY_TO` are already
on the server from session D and are reused unchanged. `BREVO_API_KEY` is already declared
in `docker-compose.demo.yml`'s `environment:` list (the two-places rule — done in the same
commit as the transport).

Then deploy the normal way — **push to `main`** (or recreate backend + nginx per the
playbook; `restart` reuses old env values and is never enough). After it settles, **read
the value back from inside the running container** — the file proving correct while the
container never saw the key is exactly the failure logged twice in `ERROR_LOG.md`:

```bash
docker exec pos-system-backend-1 python -c \
  "from app.config import settings; print(settings.email_configured, bool(settings.BREVO_API_KEY))"
# must print: True True
```

## Step 5 — Prove it (the only evidence is a received message)

Place a real order on `chickshackg84.com` with your own email. Expect **"we've got your
order"** immediately, then **"confirmed"** with the lead time when accepted on the tablet.
**Check the send result in the backend log before telling anyone to check an inbox.**

Then check the received message's headers:
- `DKIM-Signature` present with `d=chickshackg84.com`
- Gmail "Show original" reports **DKIM: PASS** and **DMARC: PASS**
- `SPF: fail/neutral` here is **expected and fine** — DMARC passes on DKIM alignment
- The `£` renders correctly in the body

---

## Known gaps to close later

- **`ORDER_TRACKING_BASE_URL` stays empty.** The confirmation screen is in-app state, not a
  route, so there is no URL a customer can reopen. The "Track your order" line is omitted
  until a real order-status route exists. Worth building — it is the natural fix for a
  customer who closes the tab.
- **Receiving at `orders@chickshackg84.com`** — DONE in session D via a Fasthosts forwarder
  to the Gmail Imran reads. Not a DNS change; MX untouched.
- **Only 3 of the 4 messages matter** at launch: `received`, `accepted`, `on_the_way`.
  `rejected` fires instead of `accepted`.
- **Rejection email wording** — "Nothing has been charged" stays TRUE under the manual-
  capture model (authorise at checkout, capture on Accept, cancel on Reject), so no change
  is needed. Re-check only if the capture model ever changes.
- **Mailjet cleanup** — account, two DNS TXT records and the server's `SMTP_*` keys can be
  retired once Brevo has sent real mail for a week. Low priority; they do no harm.
