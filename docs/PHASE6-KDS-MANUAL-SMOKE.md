# Phase 6 KDS Manual Smoke Checklist

Environment: frontend + backend running, authenticated user can access `/kitchen`.

## Checklist

- Open `/kitchen` and verify fullscreen board renders with 4 columns: `new`, `preparing`, `ready`, `served`.
- Change station filter and verify ticket list updates (all / dine-in / takeaway / call-center).
- Verify elapsed timer increases every minute on visible tickets.
- Click `Refresh` and verify board reloads without navigation.
- Toggle `Audio On` then create a new kitchen ticket; verify cue plays once for newly appeared `new` ticket.
- Use `Bump` on a ticket and verify it moves to the next lifecycle column/state.
- Use status buttons (`Prep`, `Ready`, `Served`) and verify only valid transitions are enabled.
- Click `Recall` and verify ticket gets highlighted and prioritized in its column; click again to clear.
- Verify unauthenticated access to `/kitchen` redirects to `/login`.
- Verify any API error appears in the top error banner.

## WebSocket Connectivity

- Open browser DevTools Network tab → WS filter before navigating to `/kitchen`.
- Verify a WebSocket connection is established to `/ws`.
- In the WS messages, verify auth handshake: client sends `{"type":"auth","token":"..."}`, server responds `{"type":"auth_ok"}`.
- Verify room join: client sends `{"type":"join","room":"kitchen:all"}`, server responds with join confirmation.
- Open `/kitchen` in a second browser tab.
- Bump a ticket in Tab 1 → verify Tab 2 updates within 1-2 seconds without manual refresh.
- Kill the backend container briefly (`docker compose stop backend`), verify the KDS shows a connection error or falls back to polling, then restart and verify reconnection.

## Expected Pass Criteria

- No runtime crash.
- No blocked UI interaction.
- Ticket actions reflect backend transition behavior.
- WebSocket events propagate between tabs in real-time.
