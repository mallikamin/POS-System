# How can an Android tablet print to a network receipt printer?

**Last updated:** 2026-07-27 (07:20 PKT)
**Why this file exists:** the question recurs at every site in the referral pipeline, and it kept
getting re-answered from scratch. This is the whole option space in one place, with the reasoning,
so nobody has to rediscover it. Decision and status live in `printing.md`; this is the *why*.

---

## The one sentence that explains everything

> **No browser on any platform can open a raw TCP socket. There is no web API for it, by design.**

A thermal receipt printer on port 9100 is a raw socket: you connect, you write ESC/POS bytes, it
prints them. That is the entire protocol. So a web page cannot talk to it directly — not with better
JavaScript, not with a framework, not with permissions, not ever.

Everything below is a way of routing around that one fact.

---

## Does a PWA help?

**No. Not even slightly, for printing.** This is worth being precise about because it looks like it
should.

Installing a PWA to the home screen gets you a fullscreen shell, an icon, a service worker, offline
caching and push notifications. It does **not** widen the security sandbox. A PWA is the same web
page with different window decoration. Specifically it still cannot open a TCP socket, and:

| Web API | Why it does not reach this printer |
|---|---|
| **Web Bluetooth** | BLE/GATT only. Receipt printers use **Classic Bluetooth SPP**, which the API cannot speak. Also demands a chooser dialog per session |
| **WebUSB** | Real, but needs the printer physically plugged into the tablet by OTG. The printer is in the kitchen on Ethernet |
| **Web Serial** | Not implemented in Chrome on Android |
| **WebSocket / WebTransport / WebRTC** | All need a *cooperating server* speaking that protocol. A dumb ESC/POS printer speaks none of them |
| **`fetch()` to `http://printer:9100`** | Sends HTTP headers into a raw port. The printer prints the headers as garbage. Also blocked by mixed content and CORS |

**But the PWA is still worth building — for the screen, not the printer.** Push notifications mean an
order can wake the tablet and make a noise without the browser being open, which is most of what
makes a Just Eat order pad feel like a Just Eat order pad. Filed as a real idea, just not an answer
to this question.

---

## The full option space

### A. No app installed at all

| # | Path | Verdict |
|---|---|---|
| A1 | `window.print()` → Android print framework → **built-in Mopria service** | ❌ **for a 9100 printer.** Mopria discovers **IPP** printers on port 631. Different protocol, different port. The printer will not appear in the list |
| A2 | Same, **but if the printer happens to speak IPP/AirPrint** | ✅ **Would actually work with no app.** Some newer units do (certain Epson TM-m30 and Star mC-Print models). Unlikely on a kitchen slip printer, but **the model number off the self-test slip answers it for free**, so it costs nothing to check |
| A3 | Web Bluetooth / WebUSB / Web Serial / raw fetch | ❌ See the table above |

**Conclusion: there is no reliable no-app path.** A2 is a free lottery ticket, nothing more.

### B. A helper app, page stays a web page ← **where we are**

| # | Path | Cost | Notes |
|---|---|---|---|
| **B1** | **RawBT via the `rawbt:` URL scheme** | £0 | ✅ **Chosen and built.** One tap, native text, we control cut and emphasis. Verified: RawBT supports Ethernet/Wi-Fi on 9100 (AppSocket) |
| **B2** | **RawBT as an Android *print service*, driven by `window.print()`** | £0 | ✅ **Plan B, same app.** Malik's suggestion, and it does work. Costs 3-4 taps per order because the print dialog opens each time, and Android renders to PDF first so the service rasterises it — slow on a cheap thermal head. Good fallback, poor primary |
| B3 | A different bridge app (POSBridge and similar) | £0 | Same shape as B1, different vendor. Useful only if RawBT disappoints. Avoids single-vendor lock-in |
| B4 | Termux running a tiny **local HTTP server**; the page calls `http://127.0.0.1:PORT` | £0 | Works in principle: `localhost` counts as a trustworthy origin so mixed content does not block it, but Chrome's **Private Network Access** rules require a preflight, and Termux has to be running. More moving parts than B1 for no gain |

### C. Wrap it in a real app

| # | Path | Cost | Notes |
|---|---|---|---|
| C1 | **Native WebView app + JS bridge to a socket** | dev time | The robust endgame, and what the competitor on the uncle's counter is almost certainly running. No dialog, no third party, can auto-print unattended, survives Doze via a foreground service. Needs signing and sideloading or a Play listing |
| C2 | Trusted Web Activity around the PWA | dev time | Gives an app shell but not an arbitrary native bridge. Wrong tool for hardware access |

### D. Take the tablet out of the loop

| # | Path | Cost | Notes |
|---|---|---|---|
| D1 | **Cloud printer** (Star CloudPRNT, Epson Server Direct Print) | ~£225 | The printer polls our server over the internet. No app, no bridge, no tablet involvement, nothing to support on his LAN. **Only option here that removes the whole problem class.** Needs a new printer, so it is off the table while his existing one works |
| D2 | Raspberry Pi bridge | ~£35-45 | Technically fine. ❌ Client has explicitly refused more hardware |
| D3 | Windows mini PC | £150-240 | Same refusal, five times the price |
| D4 | Email-to-print / Google Cloud Print | — | GCP was discontinued in 2021. Thermal slip printers do not do email |

### E. Unattended printing, no tap

| # | Path | Notes |
|---|---|---|
| E1 | Termux + Termux:Boot running a polling agent | The original plan. **Made unnecessary** by the realisation that he accepts every order by hand, so the print can ride on that tap. Android's battery killer is the risk, and it is a risk we no longer need to take |
| E2 | Native foreground service (part of C1) | The correct way to do unattended printing if it is ever actually needed |

---

## The escalation ladder

Try in this order. Stop at the first that works.

1. **B1** — `rawbt:` scheme, one tap. Built, tested, ready.
2. **B2** — `window.print()` → RawBT. Same app, no new install, just more taps.
3. **A2** — if the printer turns out to speak IPP, no app at all. Check the model number, it is free.
4. **B3** — a different bridge app, if RawBT specifically misbehaves.
5. **C1** — native WebView app. Real work, but it is the answer for the referral sites long-term.
6. **D1** — cloud printer, if a site's network defeats everything else. Costs money, ends the argument.

**We are at step 1 and steps 2 and 3 cost nothing extra to test on the same visit.**

---

## What still has to be measured, not reasoned about

Three things no amount of analysis settles:

1. **Does Chrome on his Android version honour the `rawbt:` scheme?** Scheme handling has changed
   across Chrome versions. The test page carries an `intent:` button as a second route for exactly
   this reason.
2. **Paper width.** 48 columns assumes 80 mm; 58 mm paper is 32. Get it wrong and every line is
   silently truncated by the printer. `?width=` exists and is tested.
3. **Does EposNow hold port 9100 open** between jobs? Most POS software opens, prints and closes. If
   it holds the socket, our connection is refused and we fall back to D1.

---

## The honest confidence note

Verified from vendor documentation: RawBT drives Ethernet/Wi-Fi printers on port 9100, exposes the
`rawbt:` scheme, and registers as an Android print service.

Inferred, not verified hands-on: that B2 rasterises rather than sending text. It follows from how
Android printing works — the framework always produces a PDF and hands it to the print service — but
nobody here has watched it happen. Treat "B2 is slower" as very likely rather than proven.

Not verified at all: anything about **his specific tablet, Chrome version, printer model, or
router**. That is what tomorrow is for.
