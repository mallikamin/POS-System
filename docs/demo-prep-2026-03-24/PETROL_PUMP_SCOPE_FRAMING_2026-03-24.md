# Petrol Pump POS — Scope Framing Guide

**For:** Younis Kamran team meeting, March 24, 2026
**Status:** Not built. This is a new vertical requiring formal discovery before commitment.
**Lead:** Kuwait-based petrol pump / fuel station client

---

## Position

> "We can build a petrol pump POS on the same platform foundation as the restaurant POS. The core infrastructure is proven and reusable. The fuel-station operations layer is new and needs dedicated product design. We should not commit to a timeline or price before a proper discovery session."

---

## What Carries Over From Restaurant POS (~40-50%)

These modules are built, tested, and directly reusable:

| Module | Reuse Level | Notes |
|--------|-------------|-------|
| Authentication (JWT + PIN) | Direct | Same login, same role system |
| Multi-tenant architecture | Direct | Add a new tenant for the fuel station |
| Role-based permissions | Direct | New roles (attendant, shift supervisor, etc.) |
| Staff management | Direct | Same CRUD, different role names |
| Payment processing (cash/card/split) | Direct | Same payment engine |
| Cash drawer sessions | Direct | Same open/close/reconcile flow |
| Z-Report / daily settlement | Adapted | Different line items, same structure |
| Reporting framework | Adapted | Different metrics, same engine |
| Audit logging | Direct | Same trail, different events |
| QuickBooks integration | Adapted | Different Chart of Accounts, KWD currency |
| Customer management | Adapted | Fleet/corporate customers instead of walk-ins |
| Docker/deployment infrastructure | Direct | Same deployment model |

**Value statement:** "We're not starting from scratch. Half the platform is already battle-tested."

---

## What's NOT Reusable (~50-60%)

These restaurant-specific modules don't apply to fuel stations:

| Restaurant Module | Fuel Station Equivalent | Status |
|-------------------|------------------------|--------|
| Menu categories & items | Fuel products + convenience store | Needs new design |
| Modifiers | N/A | Not applicable |
| Floor plan & tables | Pump bay layout | Needs new design |
| KDS (Kitchen Display) | N/A | Not applicable |
| Order state machine (6 states) | Pump transaction (simpler: activate → dispense → pay) | Needs new design |
| Table sessions | Shift-based attendant sessions | Needs new design |
| Dine-In / Takeaway / Call Center | Pump sales / Walk-in shop | Needs new design |

---

## Net New Capabilities Required

These don't exist in the current POS at all:

### Core Operations
- **Pump & dispenser mapping** — visual layout of pump bays, nozzle assignment
- **Volume-based billing** — liters x price/liter (not menu-item pricing)
- **Meter readings** — opening/closing nozzle readings per shift
- **Shift handover** — attendant-to-attendant accountability with readings
- **Nozzle-level control** — activate/deactivate pumps from POS

### Inventory
- **Fuel tank inventory** — track tank levels by product
- **Delivery tracking** — record fuel deliveries, reconcile against tank capacity
- **Dip-stick / wet stock reconciliation** — daily variance detection (leaks, evaporation, theft)

### Customers & Billing
- **Fleet/account customers** — credit accounts, fleet cards, plate numbers
- **Vehicle tracking** — plate number per transaction, fleet association
- **B2B invoicing** — monthly statements for corporate/fleet accounts

### Compliance (Kuwait)
- **Kuwait VAT** — different from Pakistan's FBR/PRA
- **KWD currency** — swap PKR paisa math for KWD fils math
- **Kuwait regulatory requirements** — TBD during discovery

### Hardware
- **Dispenser integration** — Gilbarco, Wayne, Tokheim, or other vendor protocols
- **Controller connectivity** — network interface to pump controllers
- **Convenience store POS** — if the station also has a retail shop

---

## Questions to Qualify the Opportunity

### Is This Real? (Commercial)

| # | Question | Why It Matters |
|---|----------|----------------|
| 1 | Active client with budget, or just exploratory? | Determines if we invest in discovery |
| 2 | Who is the decision-maker? | Need direct access, not telephone game |
| 3 | What's their expected timeline? | Sets urgency and resource planning |
| 4 | One site, multiple sites, or chain rollout? | Scope multiplier |
| 5 | Budget range? | Filters out tire-kickers |

### What Do They Operate? (Scope)

| # | Question | Why It Matters |
|---|----------|----------------|
| 6 | How many pumps per site? | Core UI and data model scope |
| 7 | How many nozzles per pump? | Determines granularity of tracking |
| 8 | Which fuel products? (petrol, diesel, premium, CNG) | Product catalog scope |
| 9 | Convenience store too, or fuel only? | Could need a full retail POS module |
| 10 | Fleet/account customer billing needed? | Adds invoicing and credit management |
| 11 | Attendant-level accountability? | Per-person shift tracking and variance |
| 12 | Shift-wise cash reconciliation? | Z-Report equivalent for fuel |
| 13 | Manual dip-stick reconciliation today? | Inventory management complexity |
| 14 | Meter reading audit trails needed? | Compliance and shrinkage control |

### What Hardware Do They Run? (Integration)

| # | Question | Why It Matters |
|---|----------|----------------|
| 15 | Dispenser vendor? (Gilbarco, Wayne, Tokheim, other) | API/protocol determines integration effort |
| 16 | Vendor API or middleware available? | Without this, pump integration is much harder |
| 17 | Controllers network-connected? | Ethernet vs serial vs no connectivity |
| 18 | What other systems already in place? | Identify integration points and replacements |

### Accounting & Compliance

| # | Question | Why It Matters |
|---|----------|----------------|
| 19 | Do they use QuickBooks? Online or Desktop? | Same QB integration path vs. new |
| 20 | Kuwait VAT requirements? | Tax engine customization |
| 21 | Cash retail only, or also B2B/fleet billing? | Invoicing scope |
| 22 | Multi-currency needed, or KWD only? | Currency engine scope |

---

## What NOT to Promise in the Room

| Do NOT promise... | Instead say... |
|-------------------|----------------|
| Live dispenser integration | "We need to confirm the vendor and API availability first." |
| A fixed project price | "We need a discovery session to scope this properly." |
| A guaranteed timeline | "Timeline depends on hardware, scope, and whether they need the convenience store module too." |
| That it's just a configuration change | "The platform foundation is reusable, but the fuel operations layer is new product work." |

---

## Recommended Answer Line

> "This is absolutely feasible on our platform. The authentication, payments, reporting, accounting, and infrastructure are proven and reusable — that's about 40-50% of the work done. The fuel-specific operations — pump control, meter readings, wet stock, fleet billing — are new product design. We should not quote a final commitment before we know the hardware vendor, number of pumps and nozzles, inventory process, billing model, and Kuwait compliance requirements. The right next step is a dedicated discovery session with the client."

---

## Rough Effort Framing (For Internal Reference Only)

Do NOT share these numbers in the meeting. Use only if pressed for a ballpark.

| Approach | Effort | Risk |
|----------|--------|------|
| New vertical on shared platform (recommended) | 8-10 weeks | Low — clean separation |
| Fork + adapt restaurant code | 6-8 weeks | Medium — fighting existing assumptions |
| Config change only | Not possible | N/A |

**Note:** These exclude dispenser integration, which depends entirely on the vendor/API situation and could add 2-6 weeks.

---

## Suggested Next Step

If the lead is serious:

1. **Younis team qualifies** the client using questions above (1-2 weeks)
2. **We run a discovery session** with the client (1-2 hours, remote or in-person)
3. **We produce a scope document** with modules, effort, timeline, and pricing
4. **Client approves SOW** before any development starts
5. **Build as a separate vertical** on the shared platform

This keeps the commitment professional and scoped, not casual.
