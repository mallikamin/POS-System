# chickshackg84.com — hosting & DNS reference

## ⚡ DNS MOVED TO CLOUDFLARE — 2026-07-27

Zone added to the Cloudflare account `mallikamiin@gmail.com` (Free plan) so the storefront Worker can
serve the apex domain. Workers custom domains require the zone to be on Cloudflare.

| | |
|---|---|
| **New nameservers** | `daisy.ns.cloudflare.com` · `vick.ns.cloudflare.com` |
| **Old nameservers (Fasthosts)** | `ns1.livedns.co.uk` · `ns2.livedns.co.uk` · `ns3.livedns.co.uk` |

### ⚠️ Cloudflare's auto-import DROPPED all four DKIM records

The import scan brought over 7 of the 11 records. **Every `livemail*._domainkey` CNAME was missing.**
Activating without noticing would have unsigned the client's outbound email and hurt deliverability.
They were re-added by hand, all set to **DNS only** (proxying a DKIM CNAME breaks it).

**Lesson: never trust a DNS auto-import. Diff it against the authoritative list, record by record,
before switching nameservers.** The list further down this file is that authoritative record.

Post-fix state: 11 records, matching Fasthosts. Email chain intact — MX + 4 DKIM + SPF + DMARC, all
`DNS only`.


**Captured 2026-07-27 from the Fasthosts panel.** Everything below is transcribed from the live
panel so **nobody has to navigate it again** — it is very slow (1.7 s for an 8 KB page from Pakistan;
RTT is a normal 144 ms, the panel itself is just heavy).

Screenshots backing every claim here are in `screenshots/` alongside this file.

---

## Headline: there is NO web hosting on this domain

| | |
|---|---|
| Package | **"Email and Web Forwarding"** — *not* web hosting |
| Package ID | `1129367388` |
| Panel URL | `admin.fasthosts.co.uk/HostingPackages/1129367388/WebForwardingWebsite` |
| Fasthosts account | `uk1517237781` |
| Domain expiry | 27-Mar-2027 |

**Consequence:** there is **no webspace, no FTP/SFTP, and no file manager.** Nothing can be uploaded
to Fasthosts. The panel's `HOSTING` button leads only to a URL-forwarding form, and the page carries
an `UPGRADE HOSTING` button — i.e. real hosting would have to be bought.

Live check 2026-07-27: `https://chickshackg84.com` returns **HTTP 404** (server answers, no site).

### Web forwarding (currently doing nothing)

- Host IP shown by Fasthosts: `88.208.252.9`
- Destination URL: **blank**
- Redirection type: **No redirect**
- **SSL: "Your website is not secured."** No certificate on this domain.

---

## The domain is already wired to Vercel

Someone has previously set this domain up on **Vercel**. Evidence, from two independent record types:

- `CNAME  www → b00d3203a061e681.vercel-dns-017.com`
- `TXT  _vercel → vc-domain-verify=chickshackg84.com,b189b3ae7e29cf232637`
- `TXT  _vercel → vc-domain-verify=www.chickshackg84.com,9bc4bb9b0efd0ced4677`
- `A    @ → 216.198.79.1` (consistent with Vercel, not with the `88.208.252.9` Fasthosts forwarding IP)

⚠️ **Ask Imran who set this up.** Most likely the *"local guy from the area"* he said had been
*"messing me around"*. Two things follow: (1) that person may still hold a Vercel project bound to
this domain, and (2) the 404 fits a Vercel deployment whose domain is no longer claimed by a live
project. Ownership needs settling before we repoint anything.

---

## Full DNS record set (as at 2026-07-27)

### A (1)
| Host | Points to |
|---|---|
| *(root)* | `216.198.79.1` |

### AAAA (0)
None.

### CNAME (5)
| Host | Points to | Purpose |
|---|---|---|
| `livemail1._domainkey` | `livemail1._domainkey.1404674.dkim.livemail.co.uk` | **email DKIM** |
| `livemail2._domainkey` | `livemail2._domainkey.1404674.dkim.livemail.co.uk` | **email DKIM** |
| `livemail3._domainkey` | `livemail3._domainkey.1404674.dkim.livemail.co.uk` | **email DKIM** |
| `livemail4._domainkey` | `livemail4._domainkey.1404674.dkim.livemail.co.uk` | **email DKIM** |
| `www` | `b00d3203a061e681.vercel-dns-017.com` | Vercel |

### MX (1)
| Host | Points to | Priority |
|---|---|---|
| *(root)* | `mailserver.livemail.co.uk` | 10 |

### SRV (0)
None.

### TXT (4)
| Host | Value | Purpose |
|---|---|---|
| `_vercel` | `vc-domain-verify=chickshackg84.com,b189b3ae7e29cf232637` | Vercel |
| `_vercel` | `vc-domain-verify=www.chickshackg84.com,9bc4bb9b0efd0ced4677` | Vercel |
| *(root)* | `v=spf1 mx a include:_spf.livemail.co.uk ~all` | **email SPF** |
| `_dmarc` | `v=DMARC1; p=none;` | **email DMARC** |

### CAA (0)
None. (Worth knowing: with no CAA record, any CA can issue for this domain, so Let's Encrypt will
work without adding one.)

---

## ⚠️ DO NOT TOUCH — live email

`chickshackg84.com` has **working email** on Fasthosts' livemail platform. These records carry it:

- `MX → mailserver.livemail.co.uk`
- the four `livemail*._domainkey` CNAMEs (DKIM)
- the root `v=spf1 ... include:_spf.livemail.co.uk ~all` TXT (SPF)
- `_dmarc` TXT

**Breaking any of these silently kills the client's email.** When we repoint the site, the *only*
records that change are:

- the **A record** at root
- the **`www` CNAME**

Nothing else. The two `_vercel` TXT records become dead weight once we move off Vercel and can be
removed later, but leaving them causes no harm.

---

## Deployment options

Given there is no Fasthosts webspace, three routes:

| # | Route | Cost | Notes |
|---|---|---|---|
| **A** | **Host the storefront on our own VPS**, behind the nginx already running the POS | £0 extra | **Recommended.** Same origin as the API (no CORS), one Let's Encrypt cert, one deploy path, no third-party account, nothing for the client to buy. Change the A record to our server IP, point `www` at it too. |
| B | Deploy to Vercel under *our* account | £0 (hobby/pro) | DNS is already shaped for it. Needs replacing the `_vercel` verify TXT records with ours, and resolving who owns the existing Vercel project. Adds a vendor and splits the stack across two places. |
| C | Buy Fasthosts hosting (`UPGRADE HOSTING`) | client pays | Shared hosting, poorly suited to a React SPA + API. No reason to choose this. |

**Recommendation: A.** We already run nginx with certbot on the VPS for the POS. Serving the
storefront from the same box means one certificate, one deployment, same-origin API calls, and
nothing extra for Imran to pay for or manage.

---

## Open questions for Imran

1. **Who set up the Vercel deployment on this domain?** Is that the developer who was
   *"messing you around"*? Does he still have access?
2. Is the email on this domain actually in use, or is `chick-shack.com` the one he uses for mail?
   (Records say livemail is configured either way — treat it as live until he confirms otherwise.)
3. Still outstanding: the **menu**.
