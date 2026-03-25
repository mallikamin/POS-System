# Younis Team Demo Plan - Mar 24, 2026

## Meeting Context

- **When:** Tuesday, Mar 24, 2026
- **Audience:** Younis Kamran + business team
- **Primary demo target:** screen demo and discussion
- **Live environment:** production first, local Docker as backup
- **Print material:** optional only for what is already built today, mainly restaurant POS + QuickBooks Online

## Purpose

Prepare for the in-person meeting with Younis Kamran's team.

This document covers three separate tracks:

1. What we should demo live today for the existing restaurant POS and QuickBooks Online.
2. What we should discuss for QuickBooks Desktop, since it is not built yet.
3. What we should discuss for the Kuwait petrol pump opportunity, since that is a new vertical on the shared platform.

## Ground Rules

- Demo live only what already exists and is stable.
- Do not imply that QB Desktop is already built.
- Do not imply that the petrol pump product already exists.
- Position QB Desktop and petrol pump as the next scoped workstreams after discovery and approval.
- Keep the story commercial and operational, not just technical.
- Because the room is business-heavy, lead with workflow, control, and readiness.
- Use technical detail only when they ask for it.

## What Exists Today

### Restaurant POS

- 98/99 formal UAT pass across 17 modules.
- BWL client review wave implemented on top of that.
- Key operational flows are in place: dine-in, takeaway, call center, kitchen, payments, refunds, reports, Z-report, waiter flow, customer flow, role/permission controls.

### QuickBooks Online

- Live admin integration surface exists.
- Actual product surfaces include:
  - Connection
  - Account Setup
  - Mappings
  - Sync
- Current capability set includes:
  - OAuth connect/disconnect
  - company status
  - Chart of Accounts snapshots
  - POS-needs matching against QB accounts
  - mapping creation and validation
  - health check
  - sync trigger
  - sync stats
  - job queue
  - sync log
  - retry failed jobs

### QuickBooks Desktop

- Discussed and architected, not implemented.
- Architecture direction already defined:
  - separate adapter
  - QB Web Connector
  - SOAP/XML polling
  - scheduled sync, not real-time
  - same POS accounting/mapping concepts where possible

### Petrol Pump / Fuel Station

- Not built.
- Shared platform reuse is meaningful for auth, tenancy, staff, permissions, payments, reporting, cash drawer, audit, QuickBooks, Z-report style closeout, and infrastructure.
- Restaurant-specific modules are not reusable as-is for fuel operations.
- Fuel-specific work requires fresh product design and discovery.

## Recommended Meeting Outcome

Walk out with these five decisions or answers:

1. Younis team signs off that the restaurant POS is demo-ready for client-facing presentation.
2. Younis team understands that QuickBooks Online is the current ready path.
3. Younis team confirms whether QB Desktop is still required.
4. If QB Desktop is required, they provide the exact version and environment details.
5. They qualify whether the Kuwait petrol pump lead is serious enough for a formal scope and SOW.

## Recommended Meeting Flow

### 75-90 Minute Version

| Time | Segment | Goal |
|------|---------|------|
| 5 min | Opening | Set expectations: live demo for restaurant POS + QB Online, discussion for QB Desktop and petrol pump |
| 35 min | Restaurant POS live demo | Prove operational readiness |
| 15 min | QuickBooks Online live demo | Prove accounting integration direction and current admin workflow |
| 10 min | QuickBooks Desktop discussion | Confirm need, constraints, and exact version |
| 15 min | Petrol pump discussion | Qualify scope, seriousness, and commercial path |
| 5-10 min | Close | Lock next actions and owners |

### 45 Minute Compressed Version

- Restaurant POS core flow: 20 min
- QB Online: 10 min
- QB Desktop: 5 min
- Petrol pump: 8 min
- Close: 2 min

## Presentation Tone For This Room

Because Younis and the business team are the primary audience:

- Spend more time on operational value than on code or architecture.
- Show "what the operator sees" and "what the owner/accountant gets."
- Avoid deep implementation language like WebSocket, Redis, polling, or adapter patterns unless asked.
- For QB Desktop and petrol pump, talk in terms of scope, risk, timeline, and dependencies.

## Pre-Demo Checklist

Do this before anyone arrives.

### System Readiness

- Demo URL loads cleanly.
- Admin login works.
- Cashier login works.
- Kitchen login or KDS screen is accessible.
- Database has enough sample orders, customers, staff, and reports data.

### Demo Data Setup

- At least one dine-in table is free and usable.
- At least one waiter exists.
- Walk-in customer default works.
- At least one order can be created and sent through kitchen.
- At least one completed order exists for refund demo.
- At least one voided order exists so reports show void data.
- Reports page has item, waiter, payment-method, and daily summary data.
- Z-report has realistic payment activity.

### QuickBooks Online Setup

- QB sandbox is already connected before the meeting.
- Account snapshots already exist.
- A completed match result already exists so you do not rely only on live processing.
- Mappings are already applied and validated.
- Sync stats and sync logs have data.
- If possible, keep the QB sandbox browser tab already open as backup proof.

### Fallback Material

- Keep UAT PDF and lean summary ready.
- Keep screenshots of evidence ready.
- Keep one backup path if live internet is unstable:
  - production first
  - local Docker second
  - screenshots/PDF third
- If you print anything, keep it limited to currently built scope:
  - restaurant POS summary
  - QuickBooks Online summary

## Part 1 - Live Demo: Restaurant POS + QB Online

## Demo Strategy

The restaurant demo should follow one operational story, not random page-hopping.

Recommended story:

"A cashier or manager logs in, takes a dine-in order, sends it to kitchen, adds another order on the same table, settles the bill, shows controls and reporting, then shows how the accounting side connects into QuickBooks."

That story covers the highest-value progress without wasting time on low-signal admin clicks.

Because this is a business-room demo, the strongest framing is:

"Here is how the restaurant runs, how management controls it, and how the accounting side connects."

## Restaurant POS Demo Script

### Step 1 - Login and role context

**Screen:** Login, then Dashboard

**Show:**

- PIN/password login
- admin vs cashier role context
- dashboard KPIs
- live operations summary

**Message to team:**

"This is already running as a multi-user, role-based operating system, not just a single counter POS."

**What they should verify:**

- authentication works
- role-based access exists
- live operational visibility exists

### Step 2 - Dine-in order creation

**Screen:** Dine-In

**Show:**

- floor/table selection
- table occupancy
- menu categories/items
- modifier selection
- waiter assignment
- walk-in customer default or customer override

**Action:**

Create a dine-in order with:

- one main item
- one item with modifiers
- assigned waiter
- default walk-in customer or searched customer

**What they should verify:**

- table-based ordering works
- waiter assignment is captured
- customer flow works
- modifier pricing is supported

### Step 3 - Kitchen flow

**Screen:** Kitchen Display

**Show:**

- order appears on KDS
- status movement through kitchen lifecycle
- real-time operational flow

**Action:**

Advance the ticket so they see the order lifecycle.

**What they should verify:**

- kitchen workflow is not theoretical
- order-to-kitchen handoff is working
- the product is operationally complete, not only admin-complete

### Step 4 - Table session / consolidated dine-in bill

**Screen:** Dine-In then settlement flow

**Show:**

- return to the same table
- add another order
- explain that table session keeps the dine-in bill consolidated

**Action:**

Create a second order on the same table so the final settlement can show combined billing.

**What they should verify:**

- the dine-in table remains operationally open
- multiple orders can roll into one final settlement

### Step 5 - Orders and order context

**Screen:** Orders page

**Show:**

- table number on order card
- waiter name on order card
- order status
- payment status
- order ticker / live queue

**What they should verify:**

- operational context is visible to staff
- the client review items around table and waiter visibility are already handled

### Step 6 - Payment and billing flow

**Screen:** Payment page or session settlement page

**Show:**

- cash vs card totals / preview
- tax behavior
- discount support
- split payment
- receipt structure
- payment lines

**Recommended flow:**

1. Open payment for the table/session.
2. Show cash total vs card total.
3. Apply a discount if you want to show the richer billing path.
4. Collect split payment or card payment.
5. Show receipt output with itemization.

**What they should verify:**

- billing is operationally complete
- taxes and discounts are not hand-wavy
- split payment and receipt detail are working

### Step 7 - Refund flow

**Screen:** Payment page on a completed order

**Show:**

- refundable balance
- refund entry
- refund note
- linked refund tracking

**What they should verify:**

- refund is a real tracked flow, not just a future item

### Step 8 - Sensitive controls and permissions

**Screen:** Orders / Payment

**Show:**

- void requires reason
- void requires password re-auth
- refund access depends on permission
- cashier/admin access differs

**Best way to present:**

- show the admin flow once
- then explain that cashier-facing controls are permission-gated

**What they should verify:**

- high-risk actions are controlled
- this is viable for real operations, not just demo operations

### Step 9 - Reports

**Screen:** Reports page

**Must show:**

- sales summary
- payment-method breakdown
- void report
- waiter performance
- top/bottom item performance

**Call out specifically:**

- net revenue
- discounts
- voided value
- waiter-wise reporting
- item-wise reporting

**What they should verify:**

- management reporting exists
- accountant-facing and operations-facing reporting both exist

### Step 10 - Z-report / shift closeout

**Screen:** Z-Report page

**Show:**

- daily settlement summary
- payment breakdown
- cash drawer / settlement alignment
- print-friendly output

**What they should verify:**

- end-of-day closeout is covered
- this is usable for actual business control, not only order taking

### Step 11 - Settings and pay-first mode

**Screen:** Settings, then quick proof in POS

**Show briefly:**

- payment flow config
- switching between order-first and pay-first logic

**Important:**

Do not spend too long here. This is a proof point, not the main story.

**What they should verify:**

- the platform is configurable for different operational models

### Step 12 - Menu / staff / floor admin surfaces

**Screen:** Admin pages

**Show briefly:**

- menu management
- staff management
- floor editor

**Important:**

This is a short confirmation pass, not a full admin training session.

**What they should verify:**

- the system is not dependent on developer-side setup for routine admin tasks

## QuickBooks Online Demo Script

This should come after the POS flow so the accounting story feels connected to real operations.

### Step 1 - Show connection status

**Screen:** Admin -> QuickBooks -> Connection

**Show:**

- connected status
- company name
- realm/company context
- last sync info

**Message:**

"The accounting connection is a first-class admin workflow, not a hidden technical integration."

### Step 2 - Show snapshots / backup discipline

**Screen:** Connection tab

**Show:**

- latest snapshots
- refresh snapshots
- export backup

**Message:**

"We are not matching directly against a mystery live state every time. We keep controlled snapshots and working copies."

### Step 3 - Show account setup / matching

**Screen:** Account Setup tab

**Show:**

- run matching flow
- coverage percentage
- matched / candidate / unmatched needs
- review decisions

**Best practice:**

Use a pre-existing match result unless you are certain live matching will complete quickly.

**Message:**

"The system understands what the POS needs to post and helps map that to the client's Chart of Accounts."

### Step 4 - Show mappings and validation

**Screen:** Mappings tab

**Show:**

- mapping list
- mapping types
- validation

**Message:**

"This is where accounting control lives. It is transparent, editable, and checkable."

### Step 5 - Show health check

**Screen:** Account Setup tab

**Show:**

- health check
- warnings or healthy state

**Message:**

"We can verify whether mappings are still good instead of hoping they remain valid over time."

### Step 6 - Show sync operations

**Screen:** Sync tab

**Show:**

- sync stats
- sync by type
- manual sync trigger
- job queue
- retry failed jobs
- sync log

**Show these sync types if available:**

- sync orders
- daily summary
- full sync

**Message:**

"The sync path is observable. We can see what ran, what failed, and what can be retried."

### Step 7 - Optional proof in actual QuickBooks

If a sandbox browser tab is ready, show one concrete result:

- Sales Receipt
- Journal Entry
- Deposit
- mapped account behavior

If not, do not fake it. Use sync logs and explain the object created.

## Recommended "Must Show" List

If time is tight, do not skip these:

1. Dine-in order creation
2. KDS handoff
3. Consolidated table settlement
4. Payment preview + split/discount/receipt
5. Refund or void control
6. Reports page
7. Z-report
8. QuickBooks connection + matching + sync

## Recommended "Nice to Show If Time" List

- Menu management CRUD
- Floor editor CRUD
- Staff management CRUD
- pay-first toggle
- call center customer flow

## What To De-Emphasize In This Meeting

Unless someone explicitly asks, do not spend much time on:

- raw architecture diagrams
- endpoint counts
- internal service breakdown
- deployment internals
- low-level QB API mechanics

Those are valid, but they are not what will win this room.

## Part 2 - QuickBooks Desktop Discussion Plan

## Positioning

Be explicit:

"QuickBooks Desktop is planned and architected, but not yet built. QuickBooks Online is the current ready path."

That keeps the conversation honest and avoids accidental over-commitment.

## What Has Already Been Brainstormed

- separate Desktop adapter alongside QB Online
- QB Web Connector based approach
- SOAP/XML polling from the POS endpoint
- scheduled sync cadence, not real-time
- reuse the same accounting-needs and mapping philosophy where possible
- support for sales receipts, payments, refunds, journal entries, and related sync logs/retries
- migration path from Desktop to Online without rewriting POS business logic

## Key QB Desktop Constraints to Explain

- Requires QuickBooks Web Connector on the client's machine.
- The machine hosting QB Desktop must be on and reachable for sync windows.
- Sync is scheduled/polled, not real-time.
- Desktop environment details matter much more than Online.
- Exact edition and year matter.

## Questions for Younis Team About QB Desktop

Ask these directly and do not move forward without the answers.

1. Does the client actually need QB Desktop, or is QB Online acceptable?
2. Which Desktop edition do they use: Pro, Premier, or Enterprise?
3. What year/version is it?
4. Is it single-user or multi-user?
5. Is the QB company file on one PC, a local server, or remote desktop?
6. Who controls/administers that machine?
7. Can a Web Connector be installed on it?
8. Does that machine stay on during business hours and overnight?
9. Do they want per-order posting or daily summary posting?
10. Do they need tax, discounts, voids, refunds, and cash over/short reflected in QB?
11. Are classes, locations, customers, or custom fields used heavily in their Desktop file?
12. Are they willing to pilot QB Online first while Desktop is separately scoped?

## Recommended QB Desktop Answer Line

"We can support QB Desktop, but it is a separate delivery track because the integration model is fundamentally different from QB Online. First we need the exact Desktop version and environment details, then we can scope the adapter and the Web Connector flow properly."

## Part 3 - Petrol Pump / Kuwait Discussion Plan

## Positioning

Frame this as a new vertical on the shared platform, not a fork of the restaurant product.

Recommended line:

"We should build the petrol pump system on the same multi-tenant core so we reuse identity, reporting, payments, accounting, and infrastructure, while replacing the restaurant-specific operations layer with fuel-station workflows."

## What Is Reusable

- auth and role-based access
- multi-tenant architecture
- staff and permissions
- payments and cash drawer patterns
- reporting framework
- Z-report / closeout style reporting logic
- audit logs
- QuickBooks integration approach
- deployment and infrastructure model

## What Is Not Reusable As-Is

- menu engine
- modifiers
- KDS
- floor plan
- tables
- restaurant order/session model

## Fuel-Specific Capabilities To Discuss

- pump and dispenser mapping
- nozzle-level control
- meter reading capture
- opening and closing readings
- shift handover
- dip-stick / wet stock reconciliation
- tank inventory
- price-per-liter billing
- volume-based sales
- cash, card, account, fleet, and credit customers
- attendant assignment
- vehicle and fleet tracking
- Kuwait VAT and KWD currency support
- hardware/vendor API integration

## Questions for Younis Team About the Petrol Pump Lead

These questions decide whether the opportunity is real or still vague.

### Commercial Qualification

1. Is this an active client opportunity or just an exploratory conversation?
2. Is there a budget range?
3. Who is the decision-maker?
4. What is the expected timeline?
5. Is this one site, multiple sites, or a chain rollout?

### Operational Scope

6. How many pumps are there per site?
7. How many nozzles per pump?
8. Which fuel products are sold?
9. Do they run convenience store retail too, or fuel only?
10. Do they need fleet/account customer billing?
11. Do they need attendant-level accountability?
12. Do they need shift-wise cash reconciliation?
13. Do they already do dip-stock reconciliation manually?
14. Do they need meter reading audit trails?

### Hardware / Integration

15. Which dispenser vendor do they use: Gilbarco, Wayne, Tokheim, or other?
16. Is there an available vendor API, protocol, or middleware?
17. Are controllers already network-connected?
18. What other systems are already in place today?

### Accounting / Compliance

19. Do they use QuickBooks too, and if yes, Online or Desktop?
20. Do they need Kuwait VAT handling?
21. Is the invoicing flow cash retail only, or also B2B/fleet/account billing?
22. Do they need multi-currency or only KWD?

## Recommended Petrol Pump Answer Line

"This is feasible on the current platform foundation, but it is a new vertical. We should not quote a final commitment before we know the hardware vendor, number of pumps/nozzles, inventory process, billing model, and accounting/compliance requirements."

## What Not To Promise In The Room

Do not casually promise:

- live dispenser integration without vendor/API confirmation
- a fixed project price for Kuwait petrol pump before discovery
- a guaranteed timeline without site and hardware details
- that QB Desktop is already available

## Suggested Close-Out Questions

End the meeting by locking these down:

1. Are we aligned that the restaurant POS is ready for client-facing demos?
2. Do you want us to position QB Online as the primary accounting path right now?
3. Is QB Desktop still mandatory, and if yes, what exact version is in use?
4. Is the petrol pump lead serious enough for a formal discovery session?
5. Who will gather the missing client details, and by when?

## Suggested Next Actions After Meeting

### If restaurant POS + QB Online are approved

- prepare a client-facing demo version
- prepare a short one-page leave-behind
- prepare QB onboarding checklist for the target client

### If QB Desktop is confirmed

- capture exact version/environment
- produce a separate Desktop SOW and estimate
- keep Online as the recommended primary track

### If petrol pump is serious

- run a dedicated discovery session
- turn findings into a new-vertical scope document
- quote through a separate SOW, not as a casual add-on

## Short Presenter Notes

- Start with what is real and demoable.
- Use one continuous operational story.
- Keep QB Online as the ready accounting path.
- Treat QB Desktop as a scoped follow-on.
- Treat petrol pump as a qualified new vertical, not a side feature.
- Use production first for confidence, but keep local ready so internet does not control the meeting.
- If a print leave-behind is used, keep it restricted to built scope only.
