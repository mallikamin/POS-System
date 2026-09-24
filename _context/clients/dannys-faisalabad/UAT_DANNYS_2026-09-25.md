# Danny's Restaurant: UAT guide

Prepared by Sitara Infotech for the Danny's team. Built screen by screen from a live walk of the
demo shop on 25 September 2026.

**How to use this guide.** Work through each test in order on the device you will use in the
restaurant (a tablet is best). For each test, do the steps, compare with "Expected", and mark
Pass or Fail. If anything looks wrong, confusing or missing, write it in "Your notes". We want
your recommendations as much as your pass/fail marks: if your staff would do something
differently, tell us.

**Login details** are in the separate access sheet we sent you. Do not share it outside the
team.

| Result key | Meaning |
|---|---|
| Pass | Worked exactly as expected |
| Fail | Did not work, or gave the wrong result |
| Note | Worked, but you want it changed or improved |

---

## Section A: Getting in

### UAT-A1. Open the shop's login page

**Who:** anyone. **Device:** the restaurant tablet or a laptop.

**Steps**
1. Open the link from your access sheet in Chrome.
2. Wait for the page to load. Do not log in yet.

**Expected**
* A dark login screen with a large number keypad (1 to 9, 0, C to clear, and a backspace key).
* An "Enter PIN" box above the keypad and an "Enter" button below it.
* A link at the bottom: "Login with email and password instead".
* The page loads in a few seconds on the restaurant's normal internet.

**Also check**
* The keypad buttons are large enough to tap comfortably with a finger on the tablet.
* The page fits the screen without sideways scrolling.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: the heading reads "POS System" rather than Danny's name or logo. Tell us if you
> want your own name and logo on the login screen.

---

### UAT-A2. Log in with the owner PIN

**Who:** Owner / Admin. **Device:** as above.

**Steps**
1. On the keypad, enter the Owner PIN from your access sheet.
2. Press Enter.

**Expected**
* You land on "Select Order Channel" within a few seconds.
* The top bar shows the restaurant name, an "Orders" button, an "Admin" button, the current
  time (Pakistan time), the logged-in person's name, and a sign-out icon on the far right.
* Channel cards: **Dine-In**, **Takeaway**, **Call Center**, and **Foodpanda** (showing its
  commission).

**Also check**
* A wrong PIN is refused with a clear message and does not log you in. Try one wrong PIN first.
* The time in the top bar matches the clock on the wall.
* Press **C** and the backspace key while typing a PIN: C clears everything, backspace removes
  one digit.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: two extra cards ("Walk-in / Dine-in" and "Phone Delivery") appear. They duplicate
> Dine-In and Call Center and will be removed before your trial. Ignore them.

---

## Section B: Dine-in

### UAT-B1. Open the floor plan and pick a table

**Who:** Waiter or cashier.

**Steps**
1. On "Select Order Channel", tap **Dine-In**.
2. Look at the tabs across the top left (one per hall or area).
3. Tap each tab, then come back to the first.
4. Tap a green table.

**Expected**
* One tab per seating area of the restaurant. Each shows its tables with table number and
  seats.
* Green = free, amber = reserved, other colours = occupied. The selected table gets a blue
  outline and a small panel below the tables (Reserve / Mark Available and so on).
* The menu opens in the middle with category tabs (Soups, Salads, Appetizers ... Tandoor ...)
  and dish cards with photo and price.
* The right-hand panel shows "Current Order", "Walk-in Customer" and a Waiter selector.

**Also check**
* Do the areas and table numbers match your restaurant? Tell us the real layout: each hall,
  table numbers and seats per table.
* Scroll the category tabs sideways: can you reach every category?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: the layout shows "Main Hall" and "Outdoor Terrace". It will be changed to your
> real areas (for example Hall 1, Hall 2, Tree House) once you confirm them.

### UAT-B2. Build a dine-in order

**Steps**
1. With a table selected, choose a waiter from the "Waiter" list at the top right.
2. Tap three or four dishes from different categories.
3. Tap the same dish twice, then use **+** and **-** on it in the order panel.
4. Remove one dish with the **x**.

**Expected**
* Each tap adds the dish to "Current Order", with a count badge ("4 items").
* **+** / **-** change the quantity and the line price at once; **x** removes the line.
* Subtotal, tax (16%) and Total update on every change and add up correctly. Check one total
  by hand.

**Also check**
* Can you see every line of a large order (8 or more dishes) without struggling to scroll?
* Is the waiter name remembered for the table?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: (1) Half / Full karahis and handis appear as two separate dishes; they will be
> changed to one dish with a Half / Full choice. (2) The order panel is narrow and the item list
> is cramped; it will be widened, with the lower section folding away. (3) "Channel" shows "No
> channel"; it will default to dine-in automatically.

### UAT-B3. Send the order to the kitchen

**Steps**
1. Leave "How this order is handled" on **To kitchen**.
2. Tap **Send to Kitchen**.

**Expected**
* A green message: "Order #[number] sent to kitchen!" The order panel empties for the next
  round.
* A yellow **Table Session** box appears at the top: Running Total, Due, and a **Settle Table**
  button. The amount equals the order total.
* The table on the floor plan changes colour to occupied.
* The order appears on the kitchen screen (tested in Section C).

**Also check**
* Add a second round to the same table (more drinks, dessert) and send it. The Running Total
  should include both rounds.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section C: Kitchen

### UAT-C1. The order reaches the kitchen screen

**Who:** Kitchen staff (log in with the Kitchen PIN on the kitchen tablet or screen).

**Steps**
1. Open the Kitchen Display on the kitchen device.
2. Send a new dine-in order from the POS (UAT-B3) and watch the kitchen screen.

**Expected**
* Four columns: **NEW**, **PREPARING**, **READY**, **SERVED**, each with a count.
* The new order appears in NEW within a few seconds without pressing Refresh ("Realtime" shows
  green at the top).
* The ticket shows the order number, the order type, every dish with its quantity, the total,
  and a timer counting minutes since the order was placed.
* With **Audio** switched on, a sound plays when a ticket arrives.

**Also check**
* Can the chefs read the ticket from where they stand? Is the text big enough?
* Does the ticket show everything the kitchen needs (table number, waiter, special notes)?
* Try the **All Stations** filter.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: (1) the screen is dark; a lighter version is planned. (2) The ticket does not
> show the table number yet. (3) An old test ticket may show in NEW; ignore it.

### UAT-C2. Move a ticket through the kitchen

**Who:** Kitchen staff.

**Steps**
1. On the new ticket, tap **Start**.
2. When the food is cooked, tap **Bump Ready**.
3. When the waiter collects it, tap **Serve**.

**Expected**
* **Start** moves the ticket to PREPARING; the button changes to **Bump Ready**.
* **Bump Ready** moves it to READY; the button changes to **Serve**.
* **Serve** moves it to SERVED.
* Column counts update each time. The Prep / Ready / Served markers under the ticket show where
  it is.
* **Recall** moves a ticket back one step if tapped by mistake. Try it once.

**Also check**
* Does the waiter's POS show the order as ready when the kitchen bumps it?
* With two or more tickets, are the oldest ones easy to spot (timer colour)?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: after SERVED, leave the ticket alone and settle the bill at the POS (Section D).
> Do not use the kitchen's **Complete** button during this trial.

---

## Section D: Settling the bill

### UAT-D1. Open Settle Table and check the bill

**Who:** Cashier.

**Steps**
1. On the dine-in screen, select the occupied table.
2. Tap **Settle Table** in the yellow Table Session box.
3. Tap **View Receipt** and read it, then close it.

**Expected**
* "Settle Table Session" with the table number and number of orders, and the amount Due.
* **Order Breakdown**: each order on the table with Total, Paid, Due and status "unpaid".
* **Bill Totals by Payment Method**: the bill if paid in cash (16% tax) and if paid by card
  (5% tax), side by side. Check both by hand: subtotal x 1.16 and subtotal x 1.05.
* **Discounts**, **Session Totals** and **Payment Mode** (Cash / Card / Split) further down.
* The receipt shows restaurant name and address, order number, date and time, table, cashier,
  every dish with quantity and price, subtotal, tax and total, and the footer message.

**Also check**
* Is everything on the receipt what your current bills show? Tell us what is missing: NTN,
  PRA registration number, phone number, FBR/PRA invoice number, QR code, and so on.
* Is the date and time on the receipt correct?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: (1) the cash amount box may show paisa (e.g. 6893.88) while the bill shows
> 6,894; it will be rounded to whole rupees. (2) For orders placed after midnight, the order
> number may carry the previous day's date; this is being fixed.

### UAT-D2. Take a cash payment

**Steps**
1. On Settle Table, leave Payment Mode on **Cash**.
2. Type the amount the customer hands over (for example 7000) in **Tendered**.
3. Tap **Post Cash Payment**.

**Expected**
* The change to give back is shown clearly, in whole rupees.
* Session Totals: Paid equals the bill, **Due Rs 0**.
* A green **Session Fully Paid** box: "All orders are settled."
* The table turns green (free) on the floor plan.
* The order shows as **Completed** under Orders.
* The ingredients for every dish leave stock (checked in Section F, Inventory).

**Also check**
* Try **Card** on another table: the bill should use the 5% tax total.
* Try **Split** (part cash, part card) on another table.
* Try a discount before paying, with and without a note.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section E: Orders screen

### UAT-E1. Find an order and read its status

**Who:** Cashier or manager.

**Steps**
1. Tap **Orders** in the top bar.
2. Use the tabs on the right: **All**, **Active**, **In Kitchen**, **Ready**, **Completed**.
3. Find the order you just served and paid.

**Expected**
* Each order card shows the order number, channel, status, number of items, total, table,
  and how long ago it was placed.
* A paid and served dine-in order appears under **Completed**, not under Active.
* Buttons on the card match what can be done next (Mark Ready, Refund, Receipt, Void).
* **Void** asks for a manager and a reason. Do not void a real order during the trial.

**Also check**
* Is it clear which orders are paid and which are not?
* Does the order list refresh on its own when the kitchen changes something?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: a served and paid order can still show "In Kitchen" here. This is the main fix
> before your trial, and stock is not deducted until it is fixed.

---

## Section F: Owner's back office (Admin)

### UAT-F1. Admin dashboard

**Who:** Owner / Admin.

**Steps**
1. From the POS, tap **Admin** in the top bar.
2. Read the Dashboard. Tap the refresh icon at the top right.
3. Scroll the left-hand menu from top to bottom.

**Expected**
* Four figures at the top: **Today's Revenue** (with the change against yesterday), **Orders
  Today** (with how many are active and in the kitchen), **Avg Order Value**, **Table
  Utilization**.
* **Live Operations**: one card per order type with its active orders.
* **Hourly Sales** chart and **Top 5 Items** for today.
* "Today" means today in Pakistan, from midnight. Compare Today's Revenue with your own count of
  today's bills.
* The left-hand menu lists every back-office area: Menu, Staff, Customers, Settings, Reports,
  Z-Report, Ingredients, Recipes, Stock, Production, Suppliers, Purchase Orders and more.
* **Back to POS** returns to the till.

**Also check**
* Which menu entries will your team never use? Tell us and we will hide them for you.
* What else would you like to see on the owner's first screen?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: shortly after midnight, "Today" may still include yesterday's orders. This is
> being fixed.

---
