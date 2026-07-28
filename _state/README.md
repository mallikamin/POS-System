# `_state/` — how project state is organised

**If you are a fresh session starting cold, read in this order:**

1. **`STATE.md`** at the project root — the dashboard. One screen. Tells you what is green, what is
   broken, and what to do next.
2. The one `_state/` topic file covering what you are about to work on (list below).
3. `_state/open-items.md` if you are picking work, or `_state/decisions.md` before you argue with an
   existing decision.

That is enough to start. Do not read the whole folder.

---

## Why it is split this way

State used to live in a single 200-line `STATE.md` that mixed current status, historical narrative,
gap analysis and settled arguments. It became a file nobody could skim and everybody appended to, so
stale claims survived inside it for weeks.

The split follows one rule:

> **Current state lives in a file with a stable name and a timestamp inside.
> History lives in a file with a date in its name and is never edited again.**

A file named `chick-shack-uk.md` can be trusted to describe now. A file named
`2026-07-27_1830.md` describes one moment and is frozen. Never reverse that — a dated filename
holding "current" state is how a session ends up confidently reporting last month's status.

---

## The files

| File | Holds | Edit it when |
|---|---|---|
| `../STATE.md` | Dashboard: live status table, current focus, next action | Any status changes |
| `chick-shack-uk.md` | The active client workstream: what is built, what is live, what is next | You ship or discover something on this client |
| `printing.md` | Printing: what is decided, what is built, what is waiting on the client | The printing situation changes |
| `printing-options.md` | The full option space for getting an Android tablet to print, with reasoning. Reference, not status | A new option appears or one is ruled out |
| `infrastructure.md` | Servers, domains, DNS, hosting, deploy mechanics | Anything about where things run changes |
| `pos-platform.md` | Core POS product state + the honest capability gap table | A feature lands, or a doc-vs-code gap is found |
| `open-items.md` | The open/blocked register, numbered and dated | Something opens, closes, or gets reprioritised |
| `decisions.md` | Decisions made, with rationale — **including ones already argued and settled** | A decision is taken or overturned |
| `sessions/YYYY-MM-DD_HHMM.md` | What one session actually did. Frozen after writing | Never edit an old one; write a new one |

Reference material that is not status — meeting transcripts, proposals, menus, DNS record dumps,
screenshots — stays in **`_context/`**, organised by client. `_state/` answers *"where are we?"*;
`_context/` answers *"what do we know?"*.

Archived history — every superseded `PAUSE_CHECKPOINT_*` / `HANDOFF*` — is in **`docs/history/`**
with an index. It is kept in git, not deleted.

---

## Rules that keep this honest

1. **Timestamp every edit.** Each topic file carries `**Last updated:**` at the top. Bump it even
   when nothing changed, and say so ("verified, no drift"). Otherwise a future session cannot
   distinguish a freshly-checked file from a neglected one.
2. **Verify before you assert.** If a claim is verbal, unconfirmed, or inherited from an older file,
   mark it as such. Never promote an assumption to a fact by restating it confidently.
3. **On contradiction, say so out loud** and record which source won and why. Do not silently merge.
   `STATE.md` and the newest evidence win over anything older.
4. **Never edit a dated file.** If a session log was wrong, write the correction in the current
   topic file and note that the old log is superseded.
5. **A resume point that disagrees with itself is worse than none.** If two files describe the same
   thing, one of them is wrong — fix it rather than adding a third.

## Ending a session

Write `sessions/YYYY-MM-DD_HHMM.md`, update whichever topic files changed, bump `STATE.md`, and make
sure the "next action" at the bottom of `STATE.md` is something a cold session could pick up without
asking a question.
