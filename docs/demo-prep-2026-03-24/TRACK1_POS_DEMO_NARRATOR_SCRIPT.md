# Track 1 — Restaurant POS Live Demo: Narrator Script

**Presenter:** Malik Amin
**Audience:** Younis Kamran + business team
**Duration:** ~35 minutes
**Date:** Tuesday, March 24, 2026

---

## Setup (Before Meeting)

### Monitor Layout

**Option A — Malik drives, audience watches projected screen:**
- **Display 1 (projected/shared):** Browser window with POS open — this is what they see
- **Display 2 (your laptop, facing you):** This script + a second browser tab for quick navigation if needed

**Option B — Younis team drives, Malik narrates:**
- **Their screen (projected/shared):** Browser with POS open — they click, you direct
- **Your screen:** This script open — you read and direct

Either way, this script tells you exactly what to say and when.

### Browser Tabs Pre-Opened (on the demo screen)

| Tab | URL | Label It |
|-----|-----|----------|
| 1 | `https://pos-demo.duckdns.org` | POS Login |
| 2 | `https://pos-demo.duckdns.org/kitchen` | KDS (Kitchen) |
| 3 | `https://pos-demo.duckdns.org/admin/quickbooks` | QB Admin |
| 4 | `https://app.sandbox.qbo.intuit.com` | QB Sandbox |

> Keep Tab 1 active. You'll switch tabs at specific moments in the script.

---

## The Story

The entire demo follows **one story**:

> A customer walks into the restaurant. A cashier takes their dine-in order. The kitchen prepares it. The customer adds more items. The bill is settled with split payment. Then we show management what they see — reports, controls, voids, refunds — and how all of it flows into QuickBooks automatically.

That's the arc. Every step connects to the next. No random page-hopping.

---

## SCENE 1: Login & Dashboard
**Time: ~2 minutes**

---

### [ON SCREEN: Login page — PIN pad visible]

**SAY:**

> "Let's start where every shift starts — the login screen.
>
> In a restaurant, you don't want staff typing emails and passwords. They're handling food, they're rushing. So we built PIN-based login. Four digits, they're in.
>
> Let me log in as the admin."

### [ACTION: Type PIN 1234 → press Enter]

### [ON SCREEN: Dashboard loads — KPI cards, live operations, channel cards]

**SAY:**

> "This is the manager's dashboard.
>
> Top row — today's numbers at a glance: total revenue, how many orders, average order value, how many tables are occupied right now.
>
> Below that — live operations. You can see what's happening on the floor in real time, not as a report you pull at end of day.
>
> And these three cards — Dine-In, Takeaway, Call Center — these are the three ordering channels the system supports today. Each one is a different workflow tailored to how that order type actually works in a restaurant.
>
> Let's walk through the main one — dine-in."

### [ACTION: Click the **Dine-In** card]

---

## SCENE 2: Dine-In Order Creation
**Time: ~5 minutes**

---

### [ON SCREEN: Floor plan with tables — color-coded by status]

**SAY:**

> "This is the floor plan. Every table in the restaurant is here.
>
> Green means available. Red means occupied. The layout matches the actual restaurant — the manager sets this up once in the floor editor, and that's it.
>
> Let's seat a customer."

### [ACTION: Click a **green/available table** (e.g., Table 5)]

### [ON SCREEN: Order screen — menu categories on left, cart on right]

**SAY:**

> "Now we're inside the order for Table 5.
>
> Left side — the menu, organized by category. These categories and items are all managed by the restaurant admin, not by us. They can add, remove, change prices anytime.
>
> Right side — the cart. Everything we add goes here.
>
> Let me build an order."

### [ACTION: Click category **"BBQ & Grills"**]

### [ON SCREEN: Menu items appear — Chicken Tikka, Seekh Kebab, etc.]

**SAY:**

> "Here are the BBQ items. Let's add a Chicken Tikka."

### [ACTION: Click **Chicken Tikka** — it appears in cart]

**SAY:**

> "One item in the cart. Price is calculated automatically. Now let me show you something useful — modifiers."

### [ACTION: Click **"Seekh Kebab"** — modifier modal pops up]

### [ON SCREEN: Modifier modal — options like Extra Spicy, Double Portion, etc.]

**SAY:**

> "When a customer says 'I want the seekh kebab but extra spicy and double portion' — the system handles that. These are configurable modifiers. The restaurant sets them up per item or per category. Each one can have a price surcharge.
>
> Let me select Extra Spicy and Double Portion."

### [ACTION: Select **Extra Spicy** + **Double Portion** → click **Add to Cart**]

### [ON SCREEN: Cart shows Seekh Kebab with modifiers and adjusted price]

**SAY:**

> "See the cart — Seekh Kebab with both modifiers, and the price reflects the surcharges. No manual math, no mistakes.
>
> Let me add one more item."

### [ACTION: Click category **"Rice & Biryani"** → click **"Chicken Biryani"**]

### [ON SCREEN: Cart now has 3 items — subtotal, tax, total visible]

**SAY:**

> "Three items. The cart shows the subtotal, the tax breakdown — GST and PST are calculated automatically based on the restaurant's tax configuration — and the grand total.
>
> This is ready to send to the kitchen."

### [ACTION: Click **"Place Order"** button]

### [ON SCREEN: Order confirmed — order number generated, success feedback]

**SAY:**

> "Order placed. The system generated an order number — that's the reference for everything from here: kitchen, payment, reports, and QuickBooks.
>
> Now let's see what happens in the kitchen."

---

## SCENE 3: Kitchen Flow (KDS)
**Time: ~3 minutes**

---

### [ACTION: Switch to **Tab 2 — KDS / Kitchen Display**]

> **If Younis team is driving:** "Can you switch to the Kitchen tab please — the second browser tab."

### [ON SCREEN: KDS board — columns: New, Preparing, Ready, Served. New ticket visible.]

**SAY:**

> "This is the Kitchen Display System — the KDS. This is what's mounted on a screen in the kitchen.
>
> See our order just appeared in the New column. The kitchen staff didn't need to read a handwritten chit or wait for a printout. The moment the cashier placed the order, it showed up here — real-time.
>
> Each ticket shows the table number, the items, any modifiers, and a timer showing how long it's been waiting.
>
> The kitchen workflow is simple. New means it just arrived. The cook taps it to move it to Preparing."

### [ACTION: Click the **"Start"** / bump button on the ticket → moves to Preparing]

**SAY:**

> "Now it's in Preparing. The timer keeps running. When the food is done..."

### [ACTION: Click **"Ready"** / bump button → moves to Ready column]

**SAY:**

> "Ready. The front-of-house staff can see this and knows to pick up the food. And when it's served to the table..."

### [ACTION: Click **"Serve"** / bump button → moves to Served column]

**SAY:**

> "Served. That's the full kitchen lifecycle — from order placement to the plate hitting the table, tracked with timestamps at every step.
>
> This gives management actual data on kitchen performance. How long does prep take? Where are the bottlenecks? We'll see that in the reports later.
>
> Let's go back to the floor."

### [ACTION: Switch back to **Tab 1 — POS**]

---

## SCENE 4: Second Order on Same Table (Table Session)
**Time: ~2 minutes**

---

### [ON SCREEN: Floor plan — Table 5 now shows as occupied (red/orange)]

**SAY:**

> "Notice Table 5 is now marked occupied. The system tracks table status automatically based on order state.
>
> Now here's a common dine-in scenario: the customer has been eating, and they want to order dessert or another round of drinks. In a real restaurant, this happens constantly.
>
> Let me open Table 5 again."

### [ACTION: Click **Table 5** (occupied)]

### [ON SCREEN: Order screen — existing order visible, can add more items]

**SAY:**

> "We're back at Table 5. I can see what's already been ordered. Now I'll add a dessert."

### [ACTION: Click category **"Desserts"** (or **"Beverages"**) → add an item (e.g., **"Kheer"** or **"Kashmiri Chai"**)]

### [ACTION: Click **"Place Order"** → new order created on same table]

**SAY:**

> "Second order placed on the same table. When the bill comes, both orders will be consolidated into one settlement. The customer gets one bill, not two.
>
> This is how dine-in actually works — open table sessions with multiple orders rolling into one final payment.
>
> Let's look at the order management view before we settle."

---

## SCENE 5: Orders Page & Order Context
**Time: ~2 minutes**

---

### [ACTION: Navigate to **Orders** page (sidebar or top nav)]

### [ON SCREEN: Orders list — cards showing order number, table, items, status, waiter, payment status]

**SAY:**

> "This is the orders page. Every order in the system, with full context.
>
> Look at each card — you can see the order number, which table it's for, which channel it came from, what was ordered, the current status, and payment status.
>
> This is what a shift supervisor sees. At a glance, they know: what's pending in the kitchen, what's been served, what's been paid, and what's still open.
>
> You can filter by status — show me only the ones in kitchen, or only the completed ones, or only today's voids.
>
> Now let's settle the bill for our table."

---

## SCENE 6: Payment & Settlement
**Time: ~4 minutes**

---

### [ACTION: Click **"Pay"** on the order for Table 5 (or navigate to payment for that table)]

### [ON SCREEN: Payment screen — order summary, tax breakdown, payment method selection]

**SAY:**

> "This is the payment screen.
>
> Top section — the full bill. Every item, every modifier, subtotal, taxes broken out — GST, PST — and the grand total.
>
> Now the cashier selects how the customer is paying."

**SAY:**

> "Let me show you a split payment — this is common when two people share a bill.
>
> I'll put part on card and the rest in cash."

### [ACTION: Select **Card** → enter a partial amount (e.g., 500)]

### [ACTION: Select **Cash** → system calculates the remainder → enter amount tendered]

### [ON SCREEN: Payment processed — receipt appears]

**SAY:**

> "Payment processed. Split payment — card and cash — recorded as separate payment lines.
>
> And here's the receipt. Itemized — every dish, every modifier, tax lines, payment breakdown, and the restaurant's header and footer. This is what prints on the 80mm thermal printer.
>
> The order is now complete. The table frees up automatically."

### [ACTION: Close receipt / navigate back to floor plan]

### [ON SCREEN: Floor plan — Table 5 is back to green/available]

**SAY:**

> "Table 5 is available again. The full cycle is done — seating, ordering, kitchen, second round, payment, table freed. All tracked, all connected."

---

## SCENE 7: Void & Access Controls
**Time: ~3 minutes**

---

### [ACTION: Navigate to **Orders** page → find a completed or confirmed order]

**SAY:**

> "Now let me show you something important for management — how the system handles sensitive actions.
>
> Let's say a manager needs to void an order. Maybe the customer walked out, maybe there was an error."

### [ACTION: Click **"Void"** on an order]

### [ON SCREEN: Void dialog — requires reason + password re-authentication]

**SAY:**

> "Two things happen. First — the system requires a reason. You can't void without explaining why. That reason is logged permanently.
>
> Second — password re-authentication. Even though you're already logged in, the system asks you to confirm your identity again. This prevents a cashier from walking up to an unlocked terminal and voiding orders.
>
> This is a management control, not just a button."

### [ACTION: Enter reason (e.g., "Demo - customer cancelled") → enter password → confirm]

### [ON SCREEN: Order status changes to Voided (red badge)]

**SAY:**

> "Voided. Logged. Audited. And as we'll see later — this also flows to QuickBooks as a Credit Memo, so the books stay clean.
>
> The same kind of control applies to refunds — they require permission, they require a note, and they create a financial trail."

---

## SCENE 8: Refund Flow
**Time: ~2 minutes**

---

### [ACTION: Find a **Completed + Paid** order → click **"Refund"**]

### [ON SCREEN: Refund dialog — refundable amount, refund input, note field]

**SAY:**

> "Here's a refund scenario. The customer already paid, but they're complaining about one dish. The manager issues a partial refund.
>
> The system shows the refundable balance — you can't refund more than what was paid. I'll enter a partial amount and a reason."

### [ACTION: Enter partial refund amount (e.g., 350) → enter note (e.g., "Cold food complaint") → process]

### [ON SCREEN: Refund processed — payment status updates]

**SAY:**

> "Refund processed. Tracked with the amount, the reason, who did it, and when. This shows up in reports and syncs to QuickBooks as a Refund Receipt.
>
> No cash goes missing without a trail."

---

## SCENE 9: Reports
**Time: ~4 minutes**

---

### [ACTION: Navigate to **Admin → Reports**]

### [ON SCREEN: Reports page — date picker, summary cards, charts, tables]

**SAY:**

> "Now let's look at what management and the accountant see.
>
> This is the reports page. Everything here is generated from the actual orders and payments — not a separate data entry.
>
> Let me walk through what's available."

### [ACTION: Point to / scroll through each section as you mention it]

**SAY:**

> "**Sales summary** — total revenue, total orders, average order value, taxes collected, discounts given. Net revenue after everything.
>
> **Payment method breakdown** — how much came in cash, how much on card. This is what the accountant needs for daily reconciliation.
>
> **Item performance** — which dishes sell the most, which ones don't move. This is how the owner decides what stays on the menu and what gets cut.
>
> **Waiter performance** — who handled how many orders, what revenue they generated. Useful for incentives and accountability.
>
> **Void report** — every voided order, with the reason and who authorized it. This is shrinkage control.
>
> **Hourly breakdown** — when are the peak hours? This drives staffing decisions.
>
> Everything here can be exported. No dependency on us to pull a report."

---

## SCENE 10: Z-Report / Daily Closeout
**Time: ~3 minutes**

---

### [ACTION: Navigate to **Admin → Z-Report**]

### [ON SCREEN: Z-Report page — daily settlement summary, payment breakdown, print button]

**SAY:**

> "This is the Z-Report — the end-of-day settlement.
>
> Every restaurant runs this at close. It tells you: how much should be in the cash drawer, how much was collected by card, how many voids, how many refunds, and what the net settlement is.
>
> This is not just a summary. This is the document the shift supervisor signs off on before handing over to the next shift or closing for the night."

### [ACTION: Point to payment breakdown, void totals, net settlement]

**SAY:**

> "Payment breakdown — cash, card, split. Void value deducted. Refund value deducted. Net settlement is what should match the actual cash count.
>
> And it's print-ready. One click, and this prints on the receipt printer or exports as a document."

### [ACTION: Click **Print** (or just show the print-ready layout)]

**SAY:**

> "This is the kind of operational control that tells a restaurant owner: your money is accounted for, every day, automatically."

---

## SCENE 11: Settings & Pay-First Mode
**Time: ~1.5 minutes**

---

### [ACTION: Navigate to **Admin → Settings**]

### [ON SCREEN: Settings page — general, tax, payment flow config]

**SAY:**

> "Quick detour into settings — I want to show one thing.
>
> The system supports two payment models. Order-first — which is what we just demoed. The customer orders, eats, then pays at the end. That's traditional dine-in.
>
> But some restaurants — especially QSR, quick service like KFC or McDonald's — run pay-first. The customer pays at the counter before the kitchen starts cooking.
>
> That toggle is right here."

### [ACTION: Point to **payment flow** setting (order_first / pay_first)]

**SAY:**

> "One configuration change. The entire flow adapts — kitchen won't fire tickets until payment is collected in pay-first mode. The restaurant owner decides which model fits their operation.
>
> I won't switch it now because we're in the middle of a live demo, but that's the flexibility built in."

---

## SCENE 12: Admin Surfaces (Quick Pass)
**Time: ~2 minutes**

---

**SAY:**

> "Before we move to the QuickBooks accounting side, let me do a quick pass through the admin tools — just to show that the restaurant can manage itself without calling a developer."

### [ACTION: Navigate to **Admin → Menu Management**]

**SAY:**

> "Menu management — categories, items, modifiers, pricing. The restaurant admin adds, edits, removes menu items themselves. No code change needed."

### [ACTION: Navigate to **Admin → Staff Management**]

**SAY:**

> "Staff management — create users, assign roles, set PINs, toggle active/inactive. When someone joins or leaves, the manager handles it."

### [ACTION: Navigate to **Admin → Floor Editor** (briefly)]

**SAY:**

> "Floor editor — drag-and-drop table layout. If the restaurant rearranges furniture, they update it here. Tables, positions, shapes, labels — all self-service.
>
> That covers the restaurant POS. Every operational flow from login to closeout. Now let me show you how all of this connects to the accounting side — QuickBooks."

---

## [TRANSITION TO TRACK 2: QB ONLINE]

> At this point, switch to the QB Online script: `QB_ONLINE_DEMO_SCENARIOS_2026-03-24.md`
>
> **SAY:** "Now — everything we just did, the orders, the payments, the voids, the refunds — all of that flows into QuickBooks automatically. Let me show you how."
>
> Switch to **Tab 3 — QB Admin page**.

---

## Timing Summary

| Scene | What | Target Time |
|-------|------|-------------|
| 1 | Login & Dashboard | 2 min |
| 2 | Dine-In Order Creation | 5 min |
| 3 | Kitchen (KDS) | 3 min |
| 4 | Second Order on Same Table | 2 min |
| 5 | Orders Page | 2 min |
| 6 | Payment & Settlement | 4 min |
| 7 | Void & Access Controls | 3 min |
| 8 | Refund | 2 min |
| 9 | Reports | 4 min |
| 10 | Z-Report | 3 min |
| 11 | Settings / Pay-First | 1.5 min |
| 12 | Admin Surfaces | 2 min |
| **Total** | | **~33.5 min** |

---

## If You Need to Cut Time (20-Minute Version)

Drop these scenes:
- Scene 4 (second order on same table) — mention verbally instead
- Scene 8 (refund) — mention verbally after void
- Scene 11 (settings / pay-first) — skip entirely
- Scene 12 (admin surfaces) — skip entirely

That gets you to ~20 minutes with the core story intact.

---

## Emergency Fallbacks

| Problem | Fallback |
|---------|----------|
| Production server is slow | Switch to local Docker (have it running) |
| Internet drops mid-demo | Switch to local Docker |
| KDS doesn't show ticket | Refresh KDS tab, explain "real-time sync, slight demo delay" |
| Payment fails | Show an existing completed order's receipt instead |
| QB sandbox unreachable | Use POS sync logs as proof (see QB script) |

---

## Tone Reminders

- **You are narrating a workflow, not listing features.**
- Every screen connects to the next. Never say "and also we have..."
- If Younis team asks a question, answer it, then say "let me show you" and continue the story.
- If they want to explore something, let them — then gently bring it back: "Great question. Now let me continue where we were..."
- Confidence, not salesmanship. The product speaks.
