# Tuesday Meeting Prep Checklist — March 24, 2026

**Meeting:** Younis Kamran + business team
**Location:** In-person
**Duration:** 75-90 minutes
**Demo environment:** pos-demo.duckdns.org (primary), local Docker (backup)

---

## T-60 Minutes (Before Anyone Arrives)

### System Health

- [ ] SSH into server: `ssh root@159.65.158.26`
- [ ] All 5 containers healthy: `docker compose -f docker-compose.demo.yml ps`
- [ ] Backend health: `curl https://pos-demo.duckdns.org/api/v1/health`
- [ ] Frontend loads: open `https://pos-demo.duckdns.org` in browser
- [ ] WebSocket working: check browser console for WS connection on KDS page

### Login Verification

- [ ] Admin login works: admin@demo.com / admin123 (or PIN 1234)
- [ ] Cashier login works: cashier@demo.com / cashier123 (or PIN 5678)
- [ ] KDS page accessible (kitchen@demo.com or direct URL)

### Demo Data

- [ ] At least 1 free dine-in table (check Floor Plan)
- [ ] At least 1 waiter exists in staff list
- [ ] Menu items have images and prices (check BBQ & Grills, Rice & Biryani categories)
- [ ] At least 3 completed+paid orders exist (for reports / refund demo)
- [ ] At least 1 voided order exists (for reports / void demo)
- [ ] Reports page shows meaningful data (sales summary, item performance, waiter data)
- [ ] Z-Report has realistic daily settlement data

### QuickBooks Online

- [ ] QB admin page shows "Connected" with green badge
- [ ] Company name shows: "Younis Kamran Demo Restaurant"
- [ ] Account Setup shows Grade A, 18/18 matched
- [ ] Mappings tab shows all mappings, Validate = green
- [ ] Sync tab has stats (total synced > 0, sync-by-type populated)
- [ ] Audit Log has entries showing successful syncs
- [ ] QB Sandbox browser tab open: https://app.sandbox.qbo.intuit.com
- [ ] QB Sandbox shows existing SalesReceipts from previous syncs

### Browser Setup

Open these tabs (in order):

| Tab | URL | Purpose |
|-----|-----|---------|
| 1 | `https://pos-demo.duckdns.org` | POS login / demo |
| 2 | `https://app.sandbox.qbo.intuit.com` | QB sandbox proof |
| 3 | POS Admin → QuickBooks page | QB admin walkthrough |

### Backup Readiness

- [ ] Local Docker environment starts: `docker compose up -d` on your laptop
- [ ] UAT summary PDF ready (digital, in case of questions)
- [ ] Screenshots of QB sync evidence saved (in case sandbox is slow)

---

## T-30 Minutes (Final Check)

### Quick Smoke Test

- [ ] Create a test dine-in order (table, item, modifier, place order)
- [ ] Verify it appears on Orders page
- [ ] Verify KDS receives the ticket
- [ ] Cancel/void the test order (or leave it for demo)
- [ ] QB Sync tab → trigger a quick sync to verify connection is live

### Print Materials (Optional — Only Built Scope)

If printing leave-behinds:

- [ ] Restaurant POS summary (1 page: features, channels, modules)
- [ ] QB Online summary (1 page: connection, matching, sync, audit trail)
- [ ] Do NOT print QB Desktop or Petrol Pump materials (not built yet)

---

## Meeting Materials Reference

| Document | Location | Purpose |
|----------|----------|---------|
| Main Demo Plan | `docs/YOUNIS_TEAM_DEMO_PLAN_2026-03-24.md` | Full meeting script |
| QB Online Scenarios | `docs/QB_ONLINE_DEMO_SCENARIOS_2026-03-24.md` | Click-by-click QB walkthrough |
| QB Desktop One-Pager | `docs/QB_DESKTOP_ONEPAGER_2026-03-24.md` | Discussion guide for QB Desktop |
| Petrol Pump Framing | `docs/PETROL_PUMP_SCOPE_FRAMING_2026-03-24.md` | Discussion guide for Kuwait lead |
| UAT Results | `UAT_Sitara_POS_BPO_World_Lean_2026-03-08.pdf` | 98/99 pass evidence |
| Enhancement Backlog | `ENHANCEMENT_BACKLOG.md` | Open items (if asked) |

---

## 5 Decisions to Lock Before Leaving

Walk out of this meeting with clear answers to:

| # | Decision | Owner |
|---|----------|-------|
| 1 | Is the restaurant POS demo-ready for client-facing presentation? | Younis team |
| 2 | Is QB Online the primary accounting path right now? | Younis team |
| 3 | Is QB Desktop still required? If yes — which exact version and environment? | Younis team / client |
| 4 | Is the Kuwait petrol pump lead serious enough for formal discovery? | Younis team |
| 5 | Who gathers the missing client details (QB version, pump count, etc.) and by when? | Assign in room |

---

## Post-Meeting Actions

### If restaurant POS + QB Online approved:
- Prepare client-facing demo version (clean data, branded)
- Prepare QB onboarding checklist for target client
- Schedule client demo date

### If QB Desktop confirmed:
- Capture exact version/environment from answers
- Produce Desktop SOW and estimate (~4 weeks)
- Keep Online as recommended primary track

### If petrol pump is serious:
- Schedule dedicated discovery session
- Produce new-vertical scope document
- Quote through separate SOW

### Always:
- Send meeting summary within 24 hours
- Log all decisions in project folder
- Update MEMORY.md with outcomes
