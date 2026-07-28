# Imran voice note — 2026-07-27 06:05 (WhatsApp)

**Audio:** `2026-07-27_imran_no-extra-hardware.ogg` (2m 18s)
**Transcribed:** 2026-07-27 06:10 PKT, faster-whisper `large-v3`, English, language confidence 1.00.
Lightly punctuated for readability. Nothing added or removed.

---

> Right, um, just to clarify — I know what you're talking about, because at my previous restaurant,
> Chicaros, we used to have a Windows POS system and we also had a separate computer which was in the
> office, where the guys could practically log in through AnyDesk and kind of sort the menu out, or
> any bugs etc. that we were facing. So I kind of understand what you're trying to say, um, having a
> separate kind of PC for that.
>
> However, with this kind of setup I have now, **I'm trying to avoid having any more kind of hardware
> etc.**, because I'm just trying to make it a very basic system for now, because obviously I'm locked
> in with EposNow and this system is locked.
>
> And this tablet that I have — **my uncle has the exact same setup through another provider in the
> UK**, where he's got the exact same tablet, which is connected [to a] printer. When an order comes
> in he either accepts or rejects, and he can change the kind of lead time for the delivery, or the
> time for collection. So that's practically what I was looking for — quite a basic kind of setup.
>
> Let me know if we're on the same page here. If not, then obviously we need to discuss further. But
> yeah, that's literally what I was looking for — just a very basic system separate to EposNow.
>
> Now obviously the EposNow kitchen printer **is not going to be compatible** with what we're trying
> to do. I thought it would be before, but clearly not. So I'm going to have to get a separate
> printer. If obviously I need to get a computer — I'm highly trying to avoid this, but if I have to
> do it, then we're going to have to do it.

---

## What this establishes

1. **He does not want another box.** Said twice, and "highly trying to avoid" the PC. A Raspberry Pi
   is still a box. Any solution that ships hardware is working against a stated preference, not into
   a vacuum.
2. **He already understands remote support**, having run AnyDesk on an office PC at his previous
   restaurant (Chicaros). The concept needed no selling — the *extra hardware* is the objection, not
   the remote-access idea.
3. **There is a working reference implementation in his own family.** His uncle runs the same shape
   through a different UK provider: one tablet, connected to a printer, accept/reject, adjustable
   lead time for delivery or collection. That is an existence proof that a tablet-plus-printer bridge
   with no PC is a shipped, working product in this market.
4. **He has concluded the EposNow kitchen printer cannot be shared** and expects to buy a second
   printer. ⚠️ **This directly contradicts our own resolved position** — see `_state/printing.md`.
5. **The feature set he described is exactly items 6 and 10** on the build list: accept/reject with an
   ETA, on a tablet order queue. Those are already built server-side.

## ⚠️ Contradiction to resolve — the uncle

`_state/chick-shack-uk.md` records the uncle as **Ali Fish and Chips, "no EPOS at all, pen and paper,
currently being messed around by a local developer."** This note says the uncle has a tablet and
printer from another UK provider and it works. Both cannot describe the same person and setup.

Either there are two uncles, or one of the two records is wrong. It matters commercially: an uncle
already served by a working competitor is a much weaker lead than one running on pen and paper, and
that lead is part of the ~6-site referral pipeline the £300/£35 pricing is anchored against.
**Ask before counting him as a prospect.**
