# Email setup runbook — `orders@chickshackg84.com`

**Status:** not started. Nothing sends today. **Chosen provider: Mailjet free.**
Written 2026-07-29. Code side is done (`e0168c4`); only the account + DNS + env remain.

**✅ The send path itself is now proven (2026-07-29, session D).** `send_order_email` was run
against a local SMTP sink and asserted on the bytes that actually reached the server, so the
only unknown left after your DNS work is the credentials. All four messages plus the
collection variant put a well-formed message on the wire, with `From: Chick Shack
<orders@chickshackg84.com>`, a distinct `Reply-To`, the order number in the subject and the
`£` intact. The four guards hold: no address → no send, unknown event → `False`, unconfigured
→ `False`, and a **dead mail server is swallowed** rather than failing the order.
⚠️ One thing to eyeball at Step 5: most bodies go out `Content-Transfer-Encoding: 8bit`
(raw UTF-8). Mailjet advertises `8BITMIME` so this is fine, but **confirm the `£` renders in
the mail you actually receive** rather than assuming it.

---

## The one thing that makes this safe

`chickshackg84.com` carries **Imran's live business email**. On 2026-07-27 a Cloudflare
auto-import silently dropped all four of its DKIM records — nothing alerts you when that
happens, mail just quietly degrades.

**Baseline re-verified against 1.1.1.1 on 2026-07-29 (session D), immediately before any
change. This is the exact record set to diff against afterwards** — do not diff from memory,
that is the 2026-07-27 lesson:

| Record | Current value | Touch it? |
|---|---|---|
| MX | `mailserver.livemail.co.uk` (pref 10) | ❌ **NEVER** |
| SPF (TXT) | `v=spf1 mx a include:_spf.livemail.co.uk ~all` | ❌ **NEVER** (see below) |
| DMARC | `v=DMARC1; p=none;` | ❌ leave |
| DKIM `livemail1._domainkey` | CNAME → `livemail1._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |
| DKIM `livemail2._domainkey` | CNAME → `livemail2._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |
| DKIM `livemail3._domainkey` | CNAME → `livemail3._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |
| DKIM `livemail4._domainkey` | CNAME → `livemail4._domainkey.1404674.dkim.livemail.co.uk` | ❌ leave |

All seven confirmed present and resolving at the time of writing. **If any of them differs
after your change, stop and restore before sending anything.**

**Everything we add is a NEW hostname. Nothing existing is modified.**

### Why we deliberately ignore Mailjet's SPF instruction

Mailjet's setup screen will tell you to add `include:spf.mailjet.com` to your SPF record.
**Do not.** A domain may have only **one** SPF record, so that means *editing* the live one —
the single change that could damage his real mail.

It buys us nothing: **DMARC passes if SPF *or* DKIM aligns — it is an OR, not an AND.** Our
DKIM signature will carry `d=chickshackg84.com`, which aligns with the From address, so DMARC
passes on DKIM alone. Mailjet may show the domain as "SPF not configured"; that is expected
and acceptable. (Mailjet's own docs note SPF *alignment* needs a custom Return-Path, which is
a paid feature — another reason not to chase it.)

If deliverability ever proves poor, editing SPF is a **separate, later, deliberate** change:
copy the exact existing string first, add one `include:`, and re-verify MX + all four DKIM
selectors afterwards.

---

## Step 1 — Mailjet account (you)

1. Sign up at <https://www.mailjet.com/> — free plan, **no credit card**.
   6,000 emails/month, **200/day**. At 3 emails per order that is ~66 orders/day, well beyond
   launch volume. If we ever approach it, switching provider is an env change, not a code one.
2. **Account Settings → Domains and Senders → Add domain** → `chickshackg84.com`
3. Choose **DKIM authentication**. Mailjet shows a TXT record. Note the selector and value.
4. **Account Settings → SMTP** — note the SMTP host, port, API key (username) and secret key
   (password). **Do not paste them into chat.** They go straight onto the server (Step 4).

## Step 2 — DNS in Cloudflare (you)

Add **two** records — both on **new** hostnames, so nothing existing is modified.

> ⚠️ **Corrected 2026-07-29 (session D).** This section originally said *one* record. In
> practice Mailjet asks for domain **ownership** verification first, and DKIM second. The
> safety property is unchanged (both are additive, nothing existing is edited), but the count
> was wrong.

**2a — Ownership verification.** Mailjet offers a file upload *or* a DNS record. **Take the
DNS record.** The file route would mean deploying a file to the client's live storefront, and
a storefront deploy is a business event (it is the live ordering site), not a verification step.

| Type | Name | Value | Proxy |
|---|---|---|---|
| TXT | `mailjet._<token prefix>` (exact name Mailjet gives) | the token Mailjet gives | DNS only |

**2b — DKIM.**

| Type | Name | Value | Proxy |
|---|---|---|---|
| TXT | `mailjet._domainkey` (exact name Mailjet gives) | the long `k=rsa; p=…` string Mailjet gives | DNS only |

⚠️ Cloudflare appends the zone automatically — enter `mailjet._domainkey`, **not**
`mailjet._domainkey.chickshackg84.com`, or you create `…_domainkey.chickshackg84.com.chickshackg84.com`.

⚠️ Do **not** enable the orange proxy cloud on a TXT record.

Then in Mailjet, click **Check now** on the domain.

## Step 3 — Verify DNS before going further (either of us)

```bash
# The new DKIM record must resolve
nslookup -type=TXT mailjet._domainkey.chickshackg84.com 1.1.1.1

# NOTHING BELOW MAY HAVE CHANGED. Run it and compare to the table above.
nslookup -type=MX  chickshackg84.com 1.1.1.1
nslookup -type=TXT chickshackg84.com 1.1.1.1
for s in livemail1 livemail2 livemail3 livemail4; do
  nslookup -type=CNAME $s._domainkey.chickshackg84.com 1.1.1.1
done
```

**If MX, SPF or any of the four `livemail*` selectors changed, stop and restore before
sending anything.** This is the 2026-07-27 lesson: verify the records you did *not* intend to
touch, not just the one you added.

## Step 4 — Server env (me, or you)

On `159.65.158.26`, in `~/pos-system`, add to the production env file — **back it up first**:

```
SMTP_HOST=<from Mailjet>
SMTP_PORT=587
SMTP_USERNAME=<Mailjet API key>
SMTP_PASSWORD=<Mailjet secret key>
SMTP_STARTTLS=true
SMTP_SSL=false
EMAIL_FROM=orders@chickshackg84.com
EMAIL_FROM_NAME=Chick Shack
EMAIL_REPLY_TO=<an address Imran actually reads>
```

Then recreate the backend — **env is not hot-reloaded, `restart` reuses the old values**:

```bash
docker compose -f docker-compose.demo.yml --env-file .env.demo up -d --no-deps backend
```

Recreating the backend gives it a new IP, so **nginx must be recreated too** or it 502s.
Easiest correct route: push any commit to `main` — the deploy does all of this, including
nginx, and verifies every hostname. See `DEPLOYMENT_PLAYBOOK.md`.

## Step 5 — Prove it

Place a real order on `chickshackg84.com` with your own email. Expect **"we've got your
order"** immediately, then **"confirmed"** with the lead time when accepted on the tablet.

Then check the received message's headers:
- `DKIM-Signature` present with `d=chickshackg84.com`
- Gmail "Show original" reports **DKIM: PASS** and **DMARC: PASS**
- `SPF: fail/neutral` here is **expected and fine** — DMARC passes on DKIM alignment

---

## Known gaps to close later

- **`ORDER_TRACKING_BASE_URL` stays empty.** The confirmation screen is in-app state, not a
  route, so there is no URL a customer can reopen. The "Track your order" line is omitted
  until a real order-status route exists. Worth building — it is the natural fix for a
  customer who closes the tab.
- **Receiving at `orders@chickshackg84.com`** needs a mailbox or alias in Imran's Fasthosts /
  Livemail panel. It is **not** a DNS change and does not need MX touched.
  ⚠️ **Do NOT use Cloudflare Email Routing for this** — it requires taking over MX, which
  would break his live business email.
- **Only 3 of the 4 messages matter** at launch: `received`, `accepted`, `on_the_way`.
  `rejected` fires instead of `accepted`.
- **OI-46**: once Stripe is live, a prepaid pre-order that is rejected needs a refund, and
  the rejection email currently states "nothing has been charged".
