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

## Expected Pass Criteria

- No runtime crash.
- No blocked UI interaction.
- Ticket actions reflect backend transition behavior.
