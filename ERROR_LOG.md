# POS System Error Log

Cumulative log of errors encountered and fixed during development. Any agent (Claude, Codex, Cursor, DeepSeek) working on this project should read this file first to avoid repeating known mistakes, and append new entries when fixing errors.

---

## Format

Each entry follows:
```
### [DATE] — Short title
- **Error**: Exact error message or symptom
- **Context**: What was being done when it happened
- **Root Cause**: Why it happened
- **Fix**: What was changed
- **Rule**: What to do differently going forward
```

---

### 2026-02-20 — Floor Editor not loading
- **Error**: `/floor-editor` page blank or failing to render
- **Context**: Pre-Phase 6 stabilization — page had not been validated since Phase 4
- **Root Cause**: Stale component wiring and missing API integration after Phase 5 order changes
- **Fix**: Debugged and rewired FloorEditorPage interactions (load, drag, save, add, delete); toast noise reduced
- **Rule**: Always smoke-test affected pages after cross-cutting changes (e.g., order schema updates)

### 2026-02-20 — Dine-In POS not loading
- **Error**: `/dine-in` page broken — table selection and cart not syncing
- **Context**: Pre-Phase 6 stabilization
- **Root Cause**: Table/cart synchronization broke when Phase 5 introduced real API order submission; cart key switching (`table-{uuid}`) had race conditions
- **Fix**: Stabilized DineInPage table/cart synchronization when selection changes
- **Rule**: Multi-cart flows (dine-in table switching) must be retested after any cartStore or orderStore changes

### 2026-02-20 — Takeaway POS not loading
- **Error**: `/takeaway` page not functioning end-to-end
- **Context**: Pre-Phase 6 stabilization
- **Root Cause**: Similar to Dine-In — order submission path broke after Phase 5 API wiring
- **Fix**: Validated and fixed Takeaway ordering flow end-to-end
- **Rule**: All three POS channels (dine-in, takeaway, call-center) must be smoke-tested together after order flow changes
