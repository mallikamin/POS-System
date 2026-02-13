# Continuation Prompt — Copy This to Start Next Chat

---

## Context
QB Diagnostic & Onboarding Tool is FULLY BUILT (Session 5). All code written, needs Docker rebuild + browser testing. Detailed notes in memory files (quickbooks.md, MEMORY.md).

## What Was Done This Session (Session 5)
Built the entire QB Diagnostic & Onboarding Tool — ~3,700 lines across 6 new files + 7 modified files:

**New Backend Files:**
1. `backend/app/services/quickbooks/fuzzy_match.py` (471 lines) — Multi-signal matching engine with 33 synonym sets
2. `backend/app/services/quickbooks/diagnostic.py` (741 lines) — DiagnosticService (run, apply, health-check)
3. `backend/app/services/quickbooks/test_fixtures.py` (458 lines) — 5 mock Pakistani QB Chart of Accounts
4. `backend/app/services/quickbooks/export_pdf.py` (647 lines) — Professional 4-section PDF report
5. `backend/app/services/quickbooks/export_excel.py` (377 lines) — 3-sheet Excel workbook

**New Frontend File:**
6. `frontend/src/pages/admin/qb/DiagnosticTab.tsx` (1005 lines) — 5-step wizard UI

**Modified Files:**
- `backend/app/schemas/quickbooks.py` — 15 new Pydantic schemas
- `backend/app/api/v1/quickbooks.py` — 9 new endpoints
- `backend/requirements.txt` — added reportlab==4.1.0, openpyxl==3.1.5
- `frontend/src/types/quickbooks.ts` — 12 new TypeScript interfaces
- `frontend/src/services/quickbooksApi.ts` — 10 new API functions
- `frontend/src/stores/quickbooksStore.ts` — diagnostic state
- `frontend/src/pages/admin/QuickBooksPage.tsx` — Diagnostic tab (default)

## What To Do Next
1. **Docker rebuild**: `docker-compose build backend` (installs reportlab + openpyxl)
2. **Browser test**: Navigate to /admin/quickbooks → Diagnostic tab
3. **Test fixtures**: Run diagnostic with each of 5 fixtures against pakistani_restaurant template
4. **Verify exports**: PDF + Excel download buttons
5. **Live QB test**: Run diagnostic with real QB connection
6. **Apply flow**: Test create_new + use_existing + skip decisions
7. **Health check**: Test with live mappings

## Key Files
- Fuzzy matching: `backend/app/services/quickbooks/fuzzy_match.py`
- Diagnostic service: `backend/app/services/quickbooks/diagnostic.py`
- Test fixtures: `backend/app/services/quickbooks/test_fixtures.py`
- PDF export: `backend/app/services/quickbooks/export_pdf.py`
- Excel export: `backend/app/services/quickbooks/export_excel.py`
- Frontend wizard: `frontend/src/pages/admin/qb/DiagnosticTab.tsx`
- QB playbook memory: `.claude/projects/.../memory/quickbooks.md`

## Branch
`QuickBooks-Attempt1` — all QB work is uncommitted on this branch

## Start Command
```
The QB Diagnostic & Onboarding Tool was built last session. Docker rebuild needed (reportlab + openpyxl added). Start Docker, rebuild backend, then browser test the Diagnostic tab at /admin/quickbooks. Run diagnostic with test fixtures, verify PDF/Excel exports, then test with live QB.
```
