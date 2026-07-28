# Printing — state, constraints, and the decision still to make

**Last updated:** 2026-07-28 (20:05 PKT / 16:05 UK)
**Status:** ✅ **PROVEN ON SITE. The tablet printed to his existing EposNow kitchen printer.**
Not a plan, not an inference — paper came out. Zero hardware bought. See the block immediately below.

---

## 🎯 2026-07-28 16:00 UK — IT PRINTS. End-to-end, on the client's own hardware.

Malik walked Imran through the setup remotely over WhatsApp, one screenshot per step, ~20 minutes,
finishing minutes before the shop opened at 16:00. **RawBT's test print produced paper from the
kitchen printer, driven by the tablet.**

### What this kills, permanently

| Risk that had been open | Verdict |
|---|---|
| **EposNow holds a persistent socket on port 9100** — the last real technical unknown, and the one whose failure meant buying a second printer | ☠️ **Dead.** The tablet opened 9100 and printed while EposNow is installed and live |
| **Wireless-to-wired client isolation on the router** | ☠️ **Dead.** 5 GHz tablet → wired printer, no problem |
| Tablet and printer on different subnets | ☠️ Dead — `.153` and `.208`, same gateway |
| Whether the printer accepts jobs from anything but EposNow | ☠️ Dead |
| Whether `ESC/POS general` is the right driver | ☠️ Dead — it is the one that worked |

**Hardware cost of the printing solution: £0, confirmed rather than projected.** No Pi, no mini PC,
no second printer, nothing shipped to Scotland.

### The working configuration — record it, this is the deployment recipe

| Setting | Value |
|---|---|
| App | **RawBT print service** (`ru.a402d.rawbtprinter`), Play Store, free tier |
| Connection method | **WiFi or Ethernet** |
| IP / host | **`192.168.1.208`** (printer, static) |
| Port | **`9100`** |
| Printer driver | **`ESC/POS general`** |
| **Width (dots)** | **`576`** — ⚠️ **not RawBT's default. See below.** |
| DPI | `203dpi (1mm = 8 dots)` |
| Saved printer name | `len_printer` (RawBT's auto-fill; cosmetic) |
| Tablet | `192.168.1.153`, 5 GHz, WPA2/WPA3 |

### ⚠️ The width setting is the trap at every future site

RawBT's printer page has a **Width in dots** field. It must be **576** for an 80 mm printer.
The arithmetic is fixed, not a preference: the self-test reports **48 characters, Font A**; Font A is
**12 dots** wide; 48 × 12 = **576**. At 203 dpi that is 72 mm of printable area, which is what an
80 mm head gives you.

**`384` is the 58 mm value (32 columns).** Left at 384, the printer looks perfectly healthy — a short
test string prints fine — and then silently truncates or wraps real tickets: a customer's address
across three lines, an item name cut in half. It would surface in production, on a customer's order,
and read as our software being broken.

**Verified on site 2026-07-28** using RawBT's own ruler calibration print: the printed scale ran to
~70 mm across the paper. At 384 it would have stopped near 48 mm.

**Add this to the site-setup checklist for all ~6 referral sites.** It is the single most likely
misconfiguration, and the only one that hides.

⚠️ **RawBT's default IP is `192.168.1.1`** and it must be replaced wholesale. The failure mode to
warn about at the next site is appending rather than replacing — `192.168.1.1208` errors in a way
that looks exactly like a network fault.

### Two observations off the printed slip, neither blocking

1. **The print is faint.** Grey rather than black, which matches the self-test's own
   `Print Density: Light, Darkness 23/30`. Fine for a test, arguable for a busy kitchen under
   fluorescent light. Adjustable via the printer's DIP switches or its config utility. Raise only if
   the kitchen complains — do not touch a working printer unprompted.
2. **No "FREE VERSION" inscription appeared on this test print**, despite the app's home screen
   advertising one. Do not conclude it never appears — it may apply only to image/PDF jobs. **Confirm
   on a real ticket before go-live**, because an advert on the bottom of a customer's kitchen order
   is not something to discover in production. Paid unlock exists; treat that cost as ours.

### What is still untested

Everything above proves **RawBT ↔ printer**. It does **not** yet prove **our bytes**. Still to
verify, in one pass, using `storefront/public/print-test.html` or a `.prn` file:
- The **`£` sign** renders from CP437 `0x9C` (the riskiest single decision in `escpos.py`)
- **48-column layout** does not wrap or truncate
- **Double-height `NOT PAID` banner**, bold, and the `GS V 66 0` cut all behave
- Whether **Chrome honours the `rawbt:` URL scheme**, or whether we fall back to `intent:`

---

---

## ✅ 2026-07-28 — the printer's own self-test answers every open spec question

Two photos from Imran, archived at
`_context/clients/chick-shack-uk/refs/2026-07-28_printer-label_POS80GXn.png` and
`…_printer-selftest-slip.png`. **This is hardware-confirmed fact, not client recollection.**

### Off the label

| Field | Value |
|---|---|
| Brand / model | **eposnow-branded `POS80GXn`** thermal receipt printer |
| Interface | **USB & RS232 & LAN** |
| Paper width | **80 mm** |
| Command set | **ESC/POS** |
| Speed | 300 mm/sec |
| Cash drawer | DC24V/1A kick port (unused by us) |

### Off the self-test slip — the operationally important half

| Field | Value | Why it matters |
|---|---|---|
| **IP address** | **`192.168.1.208`** | The one thing we were blocked on. OI-33 item 1 is closed |
| **DHCP** | **Disabled — the IP is STATIC** | Better than expected. **No router reservation needed**; a reboot cannot move it |
| Netmask / gateway | `255.255.255.0` / `192.168.1.254` | Shop LAN is `192.168.1.0/24`. The tablet must hold a `192.168.1.x` address |
| MAC | `00-47-5D-66-CE-AE` | For identifying it in the router's device list |
| Protocols | TCP/IP, ports **9100** and 4000 | Raw AppSocket printing is enabled and listening. This is the path we built for |
| **Character per line** | **48 (Font A)** / 64 (Font B) | **Our 48-column default is exactly right.** Not a guess any more |
| **Default code page** | **page 0 = PC437** | **Our CP437 encoding is the printer's own power-on default** |
| ASCII font type | Font A | Matches the 48-column assumption |
| Cutter | **Yes** | Our `GS V 66 0` partial cut will work |
| Command mode | `EPSON(ESC/POS)` | Confirms the dialect we hand-rolled |
| Firmware date | 2017/08/24 | **Rules out AirPrint/IPP.** See the dead lottery ticket below |
| Print density | Light, darkness 23/30 | Minor: tickets may print faint. Adjustable later if the kitchen complains |

### What this validates in code — checked, not assumed

- **`escpos.py` sends `ESC @` (reset to power-on defaults) and never selects a codepage.** The slip
  says the power-on default *is* page 0 / PC437. So the `£` → `0x9C` decision, which was the riskiest
  guess in the module, is correct against this exact unit with no extra command.
- **`ESCPOSBuilder(width=48)` matches "48-fontA" precisely.** The `?width=32` path stays as dead
  insurance for other sites; it is not needed here.
- **`CUT = GS V 66 0`** is supported — the slip reports a cutter fitted.

### ⚰️ The AirPrint lottery ticket is dead

`printing.md` flagged a free upside: if the printer spoke IPP/AirPrint, Android would find it with no
app at all. It does not. The protocol line lists raw TCP/IP only, the firmware is from 2017, and
`POS80GXn` is a generic rebadged 80 mm unit. **RawBT remains the path.** No time to be spent here.

### ⚠️ Correction to this file

Further down, the 06:43 entry says the printer *"takes a DHCP address from the broadband router."*
**That is wrong** — DHCP is disabled and the address is statically assigned. The conclusion it
supported (printer is on the shop LAN, reachable by anything on that subnet) is unaffected and
actually firmer. The follow-up ask for "a DHCP reservation later" is now **moot — drop it.**

### What is still genuinely unknown — needs Imran on site

1. ~~**Is the tablet on `192.168.1.0/24`?**~~ ✅ **CONFIRMED 2026-07-28 15:52 UK**, from a photo of the
   tablet's Network details screen (`refs/2026-07-28_tablet-network-details.png`):

   | Tablet | Printer |
   |---|---|
   | IP `192.168.1.153` | IP `192.168.1.208` |
   | Gateway `192.168.1.254` | Gateway `192.168.1.254` |
   | Mask `255.255.255.0` | Mask `255.255.255.0` |

   **Identical gateway and mask, same `/24`.** They are on one LAN, and the matching gateway also
   rules out the guest-network case, which normally hands out a different range. Tablet is on **5 GHz
   Wi-Fi**, printer is wired — fine on an ordinary broadband router. The only thing that still breaks
   this is wireless-to-wired **client isolation**, which the RawBT test settles.
   *(Noted, not a problem: the tablet uses a randomised MAC. Irrelevant to printing, but any future
   DHCP reservation for the tablet must be made against that randomised address.)*
2. **Does EposNow hold a persistent socket on 9100?** Unchanged and untestable from here. The RawBT
   test settles it in one tap. **This is now the last unknown of any substance.**
3. **Does Chrome on his Android honour the `rawbt:` scheme?** The test page carries the `intent:`
   fallback for exactly this.

---

## ✅ 2026-07-27 06:43 — the deciding fact, from the client

Malik asked the one question that mattered (WhatsApp 06:40):

> *"the kitchen printer with ethernet - what is it connected to? where does the ethernet cable from
> printer go to? in the LAN or in the Eposnow till?"*

Imran, 06:43:

> **"Connected to a Ethernet switch and the switch is connected to the broadband router"**

**The printer is on the shop LAN.** It is not captive to the EposNow till. It takes a DHCP address
from the broadband router, and the tablet's Wi-Fi comes off that same router, so both sit on one
subnet. Anything on that network can open TCP:9100 and print.

**Consequences:**
- **No printer purchase.** He was about to buy one, on the strength of our own superseded advice.
- **No bridge device.** No Pi, no mini PC. The tablet he already owns is the trigger.
- **Hardware cost of the printing solution: £0.**

**Three things still to verify, none of them blocking the build:**
1. ~~**The printer's IP address.**~~ ✅ **ANSWERED 2026-07-28: `192.168.1.208`, static.** See the
   self-test block at the top of this file.
2. **Whether EposNow holds a persistent socket on 9100.** Most POS systems open, print and close. If
   it holds the port, our connect is refused. **Now testable — we have the IP.**
3. **Wireless-to-wired client isolation on the router.** Uncommon on broadband routers, but it would
   stop the Wi-Fi tablet reaching the wired printer. **Now testable.**

---

## The mechanism, decided and grounded

**Print fires on the Accept tap.** He accepts or rejects every order by hand — that is the product he
asked for — so printing does **not** need to run unattended. That single realisation removes the whole
Android-Doze problem, which was the thing we were about to spend a session testing.

**Chain:** tablet web page → `rawbt:` URL scheme → RawBT app on the tablet → TCP:9100 → printer.

Verified, not assumed: RawBT is an Android ESC/POS driver that supports **Ethernet/Wi-Fi printers on
port 9100 (AppSocket)** alongside Bluetooth and USB, and exposes a `rawbt:` URL scheme plus an
`intent:…#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;` form, with base64 payloads
recommended to be built server-side. It also registers as a handler for http/https URLs ending in
`.prn`, which is a useful fallback that avoids URL-length limits entirely.
Sources: `rawbt.ru/intents.html`, `rawbt.ru/start.html`, `github.com/402d/DemoRawBtPrinter`.
The same pattern is used by other bridge apps (e.g. POSBridge), so we are not locked to one vendor.

**Why the payload is built server-side:** ESC/POS is bytes, not text. Generating it in Python and
handing the tablet a finished base64 blob keeps the escape sequences in one testable place, keeps the
tablet dumb, and means a printer-model quirk is fixed by a deploy rather than by touching a device in
Scotland.

**No new dependency.** `python-escpos` pulls in Pillow and USB libraries for features we do not need
on a 2 GB server. A kitchen ticket needs about eight ESC/POS commands, so it is hand-rolled and unit
tested. There was no ESC/POS code anywhere in this project before today — confirmed by search — so
this is the first real printing implementation in the product, exactly as `pos-platform.md` says.

---

## ✅ Built 2026-07-27 — the printing path, waiting only on the printer's IP

| File | What |
|---|---|
| `backend/app/services/escpos.py` | ESC/POS primitives, CP437 encoding, wrapping, and a `preview()` that renders bytes as the text a printer would put on paper |
| `backend/app/services/print_service.py` | Order → kitchen ticket, plus `to_rawbt_url()` and DB assembly using the tenant's currency and timezone |
| `backend/app/api/v1/public.py` | `GET /public/manage/orders/{id}/ticket?format=rawbt\|prn\|preview` — **authenticated**, unlike the rest of that file |
| `backend/tests/test_escpos_printing.py` | 34 tests, no DB |
| `backend/tests/test_ticket_endpoint.py` | 11 integration tests, first HTTP-level tests this flow has ever had |
| `backend/app/scripts/make_print_test_page.py` | Generates the client-facing test page |
| `storefront/public/print-test.html` | **Self-contained.** No API, no login, no network. Generated, not hand-written |

Suite: **317 passing**, up from 272. The 12 failures are all pre-existing and unrelated (10 are
parked QB Desktop, 2 are stale assertions in older order tests).

### Decisions worth knowing

- **CP437, not UTF-8.** Every ticket carries a pound sign. UTF-8 `£` is two bytes and prints as two
  junk characters. CP437 has it at `0x9C`. There is a test asserting exactly that byte.
- **Local time, computed from the config's timezone at the order's own timestamp** — not "now", so a
  reprint in winter still shows the BST time it was placed at. Server is UTC, shop is Scotland.
- **The unpaid banner is double-height.** A driver who assumes an order is prepaid does not come back
  with the money, so `NOT PAID / COLLECT £39.50` is the loudest thing on the ticket.
- **The ticket endpoint requires auth.** Everything else in `public.py` is deliberately open, but a
  ticket carries a name, a phone number and a home address. Tenant isolation is tested.
- **The test page is deliberately dumb.** If it called our API, a failure could mean the API, the
  token, CORS or the printer. Static means a failure means exactly one thing.

### Three print routes, tested in order on the same visit

The test page carries all three, so one trip settles it. See `printing-options.md` for the full
option space and why everything else was ruled out.

1. **`rawbt:` scheme** — one tap, native text, our bytes. The intended path.
2. **`intent:` form** — same app, different way of invoking it, for Chrome versions that do not
   honour the custom scheme.
3. **`window.print()` → pick RawBT from the Android print dialog** — Malik's suggestion, and it does
   work. RawBT registers as an Android *print service*, so it appears in the normal print list. Costs
   3-4 taps per order and Android renders to PDF first, so it is a good fallback and a poor primary.

⚠️ **Free lottery ticket worth checking:** if the printer turns out to speak **IPP/AirPrint** (some
newer Epson TM-m30 and Star mC-Print models do), Android's built-in print service finds it with **no
app at all**. Unlikely on a kitchen slip printer, but the model number off the self-test slip answers
it for nothing.

### Two open questions the tests cannot answer

1. ~~**Paper width.**~~ ✅ **CLOSED 2026-07-28 by the self-test slip: 80 mm, 48 characters, Font A.**
   The 48-column default is confirmed against this unit. `?width=32` stays for other sites.
2. **Whether Chrome on his Android version honours the `rawbt:` scheme.** Still open. The test page
   offers the `intent:` form as a second button for exactly this reason.

**Not yet deployed.** `print-test.html` sits in `storefront/public/`. Deploying puts it on the
client's live domain, which is Malik's call, not an automatic step.

> ⚠️ **Correction, 2026-07-27 06:05 — the saving from the tablet path was overstated ~5x.**
> `HANDOFF.md` and `PAUSE_CHECKPOINT_2026-07-27-B.md` both frame the Termux spike as "avoiding a
> £150-200 mini PC". That is the number that was floated **to Imran**, and it was already superseded
> internally by the Pi decision further down this file (~£20, realistically £35-45 once you add SD
> card, PSU and case). So the honest saving is:
>
> | If the tablet works, we avoid… | Real cost avoided |
> |---|---|
> | A Raspberry Pi (our actual internal decision) | **~£35-45** per site |
> | A Windows mini PC (what was said to the client) | £150-240 per site |
>
> The tablet is still the right thing to test — it removes hardware, shipping to Scotland, and our
> setup time from every site. But across ~6 referral sites the pipeline saving is roughly **£250, not
> £1,000**, and the spike should be scoped as a couple of hours, not a couple of days. Do not repeat
> the £150-200 figure internally as if a Pi were not an option.

---

## 🔴 2026-07-27 06:05 — client voice note changes the constraints

Full transcript: `_context/clients/chick-shack-uk/voice-notes/2026-07-27_imran_no-extra-hardware.md`

### 1. "I'm trying to avoid having any more kind of hardware"

Said twice, plus *"I'm highly trying to avoid"* the PC. **This kills the Raspberry Pi as a first
choice.** A Pi is cheap but it is still a box in his kitchen, and the objection he raised is boxes,
not price. He is not haggling; he is describing the product he wants. The Pi stays as the fallback if
the tablet path fails, and it should be presented as "a matchbox that plugs into the wall", never as
"a computer".

He is not confused about what we proposed. He ran a Windows POS with an AnyDesk office PC at his
previous restaurant (Chicaros). **The remote-support concept needs no selling — the extra box is the
whole objection.**

### 2. His uncle already runs exactly what we are trying to build

> *"my uncle has the exact same setup through another provider in the UK … the exact same tablet,
> which is connected [to a] printer. When an order comes in he either accepts or rejects, and he can
> change the lead time for the delivery, or the time for collection."*

**This is an existence proof, and it is the single most useful fact in the note.** A UK competitor
ships tablet-plus-printer with no PC and no Pi, which is also how Just Eat and Uber Eats order pads
work. It means the tablet-as-bridge path is not speculative research — it is the market-standard
shape, and something on that tablet is opening a socket to that printer.

It also raises the bar. **We are now being measured against a product he has already seen working**,
not against his current absence of online ordering.

### 3. ⚠️ He thinks he must buy a second printer. We think he must not. Resolve this before he spends.

> *"obviously the EposNow kitchen printer is not going to be compatible with what we're trying to do.
> I thought it would be before, but clearly not. So I'm going to have to get a separate printer."*

**That is the opposite of what this file concluded 28 minutes earlier** (Ethernet printer, TCP:9100,
takes jobs from EposNow and from us, no purchase needed). One of the two is wrong and he is the one
holding the wallet. The standing rule applies: **never let him buy hardware without sending the link
first.** That guard already stopped one wasted purchase this week.

**The fact that decides it is one he has not given us yet:** is the kitchen printer plugged into the
**router** (on the shop LAN, so our bridge can reach it) or into the **back of the EposNow till**
(private to EposNow, so nothing else can)? "Connected to an Ethernet port" is ambiguous between the
two and we read it optimistically. **Ask for the printer's IP address.** If it has one from his
router, it is shareable. If nobody can produce one, it is not.

### 4. But a second printer may be the better answer anyway — do not reflexively talk him out of it

Sharing the EposNow printer saves £50-90 and buys three ongoing risks:

- **Unverified contention.** TCP:9100 usually accepts one socket at a time. If EposNow holds a
  persistent connection instead of closing between jobs, our connects are refused. Still unverified.
- **We inherit a dependency on a system we do not control.** An EposNow update, a re-pair or a
  swapped printer becomes our support call, on a £35/month contract.
- **Kitchen confusion.** Online orders and EposNow slips interleave on one spool.

A dedicated ~£50-90 Ethernet or WiFi thermal printer removes all three permanently, and it matches
what his uncle already runs. **Against £35/month, a one-off £50-90 to make printing independent of
the incumbent is easy to defend** — far easier than a PC.

**So the recommendation flips: the thing to argue him out of is the computer, not the printer.**

### What to actually put to him

**One tablet, one small printer, no computer.** That is his uncle's setup, it is what he asked for in
his own words, and it is the cheapest path that does not leave us supporting EposNow's hardware.
Confirm the tablet can reach the printer, and the Pi never comes up.

---

## ✅ RESOLVED 2026-07-27 05:37 — the printer is Ethernet
*(Superseded in part by the 06:05 note above — he no longer believes this printer is usable, and the
"no purchase needed" conclusion rests on an unverified reading of "connected to an Ethernet port".)*

Imran, WhatsApp: *"The kitchen printer is already connected to an Ethernet port."*

**The contradiction is settled in favour of our own discovery note.** The earlier note recorded the
kitchen printer as Ethernet; Imran's voice note said he *thought* it was Bluetooth. Our note was
right. Worth remembering as a general lesson: the client's recollection of his own hardware was
wrong, and a photo of the label would have settled it in seconds.

**Two consequences, both good:**

1. **No printer purchase.** He was about to buy a Bluetooth receipt printer, which is the one type
   that would not have worked. Caught before he spent money.
2. **The Bluetooth single-connection problem disappears entirely.** A network printer on TCP:9100
   accepts jobs from multiple systems — EposNow prints, we print, jobs queue at job boundaries.
   No contention, no pairing, no sharing conflict.

**Still required: the bridge.** Our API is on a DigitalOcean box in Singapore and cannot reach a
printer on his shop LAN. That has not changed. A **~£20 Raspberry Pi** on his network connects
outbound to us and prints to the printer's local IP.

⚠️ **Never port-forward to the printer.** Exposing a receipt printer to the internet is not an
option, whatever the convenience.

⚠️ **One thing to verify, not assume.** TCP:9100 typically accepts one socket at a time — open,
print, close. If EposNow holds a *persistent* connection rather than closing between jobs, our
connect will be refused. Most POS systems do not, so this is unlikely, but it is testable the moment
the Pi is on site and should be checked before go-live rather than discovered on the day.

**Now needed from Imran:** ✅ **ALL THREE ANSWERED 2026-07-28 — see the self-test block at the top.**
1. ~~Make and model~~ → eposnow `POS80GXn`, 80 mm, ESC/POS, LAN.
2. ~~The printer's IP address~~ → `192.168.1.208`.
3. ~~A DHCP reservation~~ → **moot, DHCP is disabled and the address is already static.**

What remains from him is not information, it is **the three print tests on site** — see OI-33.

**Confirmed 2026-07-27 05:45:** there is **no PC in the shop**, only the locked EposNow till. He does
have a **separate small Android tablet**, and has run an AnyDesk-style setup at a previous
restaurant, so the concept needed no selling.

---

## 🔬 OPEN RESEARCH: can the tablet be the bridge, and skip the mini PC?

**This is the question worth solving properly, because it recurs at every future site.**
Malik, 2026-07-27: *"i'd encourage u to explore ways of unlocking printing via the web pos."*

### Frame the problem correctly first

Earlier framing ("we need to get past NAT") was **misleading**. The bridge device already has
outbound internet. It does not need anything inbound. The actual blocker is narrower:

> **What can run code on the tablet that opens a TCP socket to the printer?**
> A browser cannot. That is the entire problem.

**Tailscale does not solve this.** It would let *our server* reach into his LAN, which is a problem we
do not have for printing. Tailscale is worth having only as *our* remote-support channel into
whatever device we end up using.

⚠️ **UNVERIFIED:** whether Tailscale on Android can act as a **subnet router**
(`--advertise-routes`). Tailscale's docs confirm Android can be an **exit node**, but exit node and
subnet router are different features and the Android case was not confirmed either way. Do not build
a plan on it without checking. Even if it works, see above: it is not the missing piece.

### Candidate paths, cheapest first

| Path | Hardware | How | Main risk |
|---|---|---|---|
| **Termux on his tablet** | **£0** | Linux environment on Android. Python script opens a socket to the printer, polls our API. `Termux:Boot` auto-starts it. **No app development.** | Android killing the process; needs wake lock + battery-optimisation exemption |
| **Minimal native Android agent** | **£0** | ~200 lines Kotlin. Foreground service with persistent notification, survives Doze properly, auto-start on boot. Not a POS app, just a print relay | Real dev + signing + sideload/Play. Most robust of the three |
| **RawBT** | **£0** | Third-party Android print app. Supports **network (TCP) printers**, not just Bluetooth. A web page hands it a job via the `rawbt:` URL scheme | Third-party freemium dependency; needs a tap per job, so poor for unattended auto-print |
| **Raspberry Pi Zero 2 W** | **~£35-45** all-in | Our internal decision before the tablet idea. Linux, so the agent is trivial and we can SSH in. See "DECIDED" below | ⚠️ **The client has explicitly asked for no more hardware.** Cheap, but still a box. Fallback only, and describe it as a matchbox, never as a computer |
| **Windows mini PC** | **£150-240** | Ordinary machine, AnyDesk, small agent. **This is the number that was floated to Imran** and it is the most expensive option on this table | ⚠️ **Effectively dead.** Most expensive, and it is the specific thing he said he is "highly trying to avoid" |

### What to actually test next session

1. **Does the tablet share a subnet with the printer?** His WiFi and the printer's ethernet almost
   certainly hit the same router, but confirm — if not, nothing tablet-side works.
2. **Termux spike.** Install Termux + Termux:Boot, write a ~30-line Python loop that opens
   `printer_ip:9100` and writes an ESC/POS test string. This single test settles the whole question.
3. **Survive Doze.** Leave it running overnight on battery-optimisation-exempt settings and see if it
   is still alive in the morning. **This, not connectivity, is what decides tablet vs mini PC.**
4. Only if 1-3 fail, order the mini PC.

### Why this matters beyond Chick Shack

Every one of the ~6 referral sites will have the same shape: a locked incumbent till, an ethernet
printer, and no spare PC. **If the tablet path works, the per-site hardware cost drops from
£150-200 to zero**, which materially changes the economics of a £300 + £35/month product. That is
worth a couple of hours of proper investigation rather than defaulting to hardware.

⚠️ **Do not quote Imran a mini PC price until the Termux spike is done.** The earlier £100-150
estimate was also optimistic for the UK — one UK data point suggested Windows mini PCs nearer £240.

---

## Where this came from

Imran, voice note 2026-07-27 04:21
(`_context/clients/chick-shack-uk/voice-notes/2026-07-27_imran_bluetooth-printer.ogg`):

> *"I do have a printer that's in the kitchen which is printing additional slips off of the EposNow
> system and I think it's a Bluetooth printer. Can we use that same printer for this as well
> alongside the EposNow, or will I have to get a separate printer?"*

**The answer given at the time was "no, you need a separate printer."** ⚠️ **That answer was wrong and
is superseded** — the printer turned out to be Ethernet (top of this file), so no purchase is needed.
The reasoning below is kept because it is correct *about Bluetooth printers* and the second point
generalises to every printing path we will ever build. It is background, not current advice.

---

## Why the existing Bluetooth printer cannot be reused

**1. Bluetooth serves one master.** Thermal receipt printers use Classic Bluetooth **SPP**, which in
practice holds **one active connection at a time**. Multiple devices can be paired, but only one
connected. If the EposNow till owns that connection our tablet cannot have it. Sharing would mean
disconnecting one system to print from the other — unworkable when both need to print live.

**2. A browser cannot drive a Bluetooth printer.** Our storefront and POS are web apps:
- **Web Bluetooth is BLE/GATT only.** It cannot speak Classic SPP, which is what receipt printers use.
- It requires a **user gesture and a device-chooser dialog**, so there is no unattended auto-print
  when an order arrives. Someone would tap through a dialog per order.

The second point generalises and is easy to forget: **a browser cannot open a raw socket to any
printer**, Bluetooth or network. Any printing path needs something other than the page itself.

---

## Two earlier contradictions — one closed, one still live

1. ~~**Bluetooth vs Ethernet.**~~ ✅ **CLOSED 2026-07-27.** It is **Ethernet**. Our discovery note was
   right and the client's recollection of his own hardware was wrong. See the top of this file.
2. ⚠️ **STILL LIVE: "no bridge needed" was wrong, and any estimate built on it is under-scoped.**
   Even an Ethernet printer sits behind the shop's NAT, and our API is on a DigitalOcean box in
   Singapore. The server cannot reach a printer on his LAN. Either something runs inside his network,
   or the printer reaches out to us. **This is exactly what the bridge question above is about, and it
   is the only part of printing that is still genuinely open.**

---

## ✅ DECIDED 2026-07-27: Raspberry Pi + Tailscale, not a cloud printer

**Prices checked, not guessed:**
- Star CloudPRNT TSP143IV: **£224.50** (Logiscenter UK)
- Generic 80 mm Ethernet ESC/POS printer: **~£50-90** (Epos Direct TP70 and equivalents)
- Raspberry Pi Zero 2 W: **~£20**

**The design:**
- A **Raspberry Pi (~£20)** sits in the shop running two things:
  1. **Tailscale** — our SSH access for support and debugging.
  2. **A small print agent (~50 lines)** holding a WebSocket to our existing POS API, writing
     ESC/POS to the printer.
- The agent connects **outbound**, so NAT is a non-issue and **no ports are opened on his router**.
  Tailscale is *not* load-bearing for printing — if the tunnel is down, printing still works. It is
  purely a support channel.
- The Pi can drive the printer over **Ethernet, USB or Bluetooth**, so almost any cheap thermal
  printer works and the model question stops being critical.

**Why not the cloud printer.** The original argument for CloudPRNT was that a local agent makes us a
support desk with no visibility into the box. **Tailscale removes exactly that objection** — we get
SSH. That leaves a £200 price difference and no remaining advantage.

**Cost to the client:**

| Scenario | Hardware |
|---|---|
| His kitchen printer has an Ethernet port | **£20** — Pi only |
| Bluetooth-only, needs a second printer | **£70-110** — Pi + generic LAN printer |
| Star CloudPRNT instead | £225, no Pi |

The middle row is the realistic case. ~£100 one-off against £35/month is defensible; £225 for a
printer is a harder conversation.

**Reuses what exists:** the POS already has WebSockets, so the agent is a client of infrastructure we
have rather than a new transport.

### Still: do not block launch on printing

The live-order tablet is what he actually asked for and is screen-first. Printing is a small
self-contained follow-on. Sequencing it that way also means go-live and payment are not held up by a
hardware question the client has not answered.

⚠️ **Client-facing framing.** Malik told Imran we would need "a cloud polling printer or some local
script at a pc on site" (WhatsApp, 2026-07-27 05:25). Correct, but **"a PC on site" oversells it** to
a takeaway owner — it sounds like cost and clutter. Lead with "a £20 device the size of a matchbox."

---

## Waiting on Imran

~~Bluetooth vs Ethernet~~ is answered. What is still outstanding is listed once, at the top of this
file under **"Now needed from Imran"**: make and model, the printer's IP address, and later a DHCP
reservation for it. Do not maintain a second list here.

---

## Wider product context

The core POS has **no real printing today** despite `CLAUDE.md:20` claiming "thermal printer support,
configurable per station." What exists is `window.print()` plus an 80 mm CSS layout
(`frontend/src/components/pos/ReceiptModal.tsx:100-131`). There is no ESC/POS, no network printer
code, no print library, and no printer field on `KitchenStation`. See `pos-platform.md`.

So whatever is built here is **the first real printing implementation in the product**, not a
configuration of something that already exists. Scope it as new work.
