# POS Project — context index

Orientation for a cold session. **This file is a map, not a source of truth.**

## Read in this order

1. **`STATE.md`** (project root) — authoritative dashboard. Always read first.
2. **`_state/README.md`** — how current state is organised, then the one topic file you need.
3. **`CLAUDE.md`** (project root) — build phases, conventions, gotchas, port map.
4. The relevant client folder below, if the work is client-facing.

**`_state/` vs `_context/`:** `_state/` answers *"where are we?"* — status, open items, decisions.
`_context/` (this folder) answers *"what do we know?"* — transcripts, proposals, menus, DNS dumps,
screenshots. Durable reference, not status. **Do not record status here**; it goes stale and
contradicts `_state/`, which is exactly what happened on 2026-07-27.

Frozen history is in **`docs/history/`**. Never current — see its `README.md` for claims that are
known false.

## Clients

| Client | Folder | Status |
|---|---|---|
| **Chick Shack UK** (Imran R) | `_context/clients/chick-shack-uk/` | **Active, building.** Proposal sent 2026-07-27. Menu received and verified against the client's official artwork. Storefront **built and deployed**; custom domain blocked on two dead Vercel DNS records. Public ordering API + Stripe not started. |
| BPO World (Younis Kamran) | `docs/` — partner pricing + MOU | Partner, 50/50 revenue share. See root `MOU-Sitara-Vera-BPO-World.md`. |
| TastyBites (Faizan) | `C:\ST\Sitara Infotech\Faizan TastyBites\` | Lead. Runs the same EposNow system as Chick Shack. |

Each client folder starts with a `README.md` that is the resume point for that client.

## Where things live

| What | Where |
|---|---|
| Current truth | `STATE.md` (root) |
| Build conventions, phases, gotchas | `CLAUDE.md` (root) |
| Client material | `_context/clients/<client>/` |
| Project-level notes / refs / screenshots | `_context/notes/`, `_context/refs/`, `_context/screenshots/` |
| Anything containing a visible secret | `_context/secrets/` — **gitignored** |
| Daily scratch | `_files/YYYY-MM/YYYY-MM-DD/` — **gitignored** |
| Stale files (moved, never deleted) | `_archive/` — **gitignored** |
| Deployment / server rules | `memory/server-deployment-rules.md` — **mandatory read before any server op** |
| Credentials master reference | `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` (root) |
| Historical checkpoints | `PAUSE_CHECKPOINT_*.md`, `HANDOFF*.md` (root) — history, not current state |

## Deliberate deviations from the standard scaffold

- **No `_context/CREDENTIALS.md`.** This project already has
  `INFRASTRUCTURE_CREDENTIALS_REFERENCE.md` at root as the master reference. A second credential
  file would create two sources of truth, which is worse than one. `_context/secrets/` still exists
  and is gitignored, for credential-bearing screenshots and files.
- **No `_context/SCHEMA.md` / `INFRA.md`.** Covered by `CLAUDE.md` (33-table schema, port map) and
  `memory/server-deployment-rules.md`. Not duplicated here.
- **Client folders under `_context/clients/`** rather than everything in a flat
  `_context/proposals/`. This project serves multiple clients; grouping by client is what makes a
  session resumable. Proposal source and rendered PDF still sit together, per the rule.
- **Project root is not yet clean.** ~80 legacy `PAUSE_CHECKPOINT_*` / `HANDOFF*` / doc files still
  sit at root from March–July. Not touched — an archive sweep needs per-file confirmation from
  Malik. Run `/hygiene sweep` when there's appetite for it.
