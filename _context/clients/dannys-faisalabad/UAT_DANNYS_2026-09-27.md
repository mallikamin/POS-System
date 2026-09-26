# Danny's Restaurant: UAT guide

Prepared by Sitara Infotech for the Danny's team. Updated 27 September 2026 from a live walk of
the demo shop. Replaces the guide of 25 September.

**How to use this guide.** Work through the tests in order on the device you will use in the
restaurant (a tablet is best; Section L repeats the key screens on a phone). For each test, do the
steps, compare with "Expected", and mark Pass, Fail or Note. We want your recommendations as much
as your marks: if your staff would do something differently, write it down.

**Login details** are in the separate access sheet we sent you. Do not share it outside the team.

**Demo data.** The shop is filled with sample dishes, recipes, stock, suppliers and a few test
orders so every screen has something to show. Nothing you do here touches a real account. Feel
free to place, pay and cancel orders.

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

**Expected**
* The Danny's logo and name above a large number keypad (1 to 9, 0, C to clear, backspace).
* An "Enter PIN" box and an "Enter" button, and a link "Login with email and password instead".

**Also check**
* The keypad is comfortable to tap with a finger. The page fits the screen without sideways
  scrolling.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-A2. Log in with the owner PIN

**Steps**
1. Try one wrong PIN first, then enter the Owner PIN from your access sheet and press Enter.

**Expected**
* The wrong PIN is refused with a clear message.
* With the right PIN you land on the channel screen: **Dine-In**, **Takeaway**, **Call Center**
  and **Foodpanda** (with its commission).
* The top bar shows the Danny's logo and name, a **Drawer** button, **Orders**, **Admin**, the
  time on a 24-hour clock (Pakistan time), the person logged in, and a sign-out icon.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section B: Dine-in order

### UAT-B1. Pick a table

**Who:** waiter or cashier.

**Steps**
1. Tap **Dine-In**. Tap each area tab (**Hall 1**, **Hall 2**, **Tree House**), then tap a green
   table.

**Expected**
* Each area shows its tables with number and seats. Green = free, red = busy, amber = reserved.
* The menu opens with category tabs and dish cards with photo and price. The right-hand panel
  shows "Current Order" and a **Waiter** list.

**Also check**
* Do the areas, table numbers and seats match your restaurant? Tell us the real layout.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: the layout is our best guess (Hall 1 with 10 tables, Hall 2 with 6, Tree House
> with 6). We will set your real layout once you confirm it.

### UAT-B2. Build the order

**Steps**
1. Choose a waiter. Add four or five dishes from different categories, including a karahi.
2. On the karahi, choose the portion (**Half** or **Full**).
3. Use **+** and **-** on one line, and remove one line.

**Expected**
* Karahis and handis ask for the portion; Full shows its extra price.
* Every added dish appears in "Current Order" and the list scrolls to it, even on a long order.
* Subtotal, GST (16%) and Total update on each change. Check one total by hand.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Question for you: the tax line says "GST (16%)". What do your current bills print (for
> example PST or Punjab Sales Tax)? We will match it.

### UAT-B3. Send it to the kitchen

**Steps**
1. Tap **Send to Kitchen**.

**Expected**
* "Order #[number] sent to kitchen!" The order number starts with today's date (YYMMDD), also
  after midnight.
* A yellow **Table Session** box shows Running Total, Due and **Settle Table**. The table turns
  red on the floor plan.

**Also check**
* Send a second round to the same table: the Running Total includes both.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section C: Kitchen

### UAT-C1. The order reaches the kitchen screen

**Who:** kitchen staff, on the kitchen screen (Kitchen PIN).

**Expected**
* Columns **NEW**, **PREPARING**, **READY**, **SERVED**. The order appears in NEW within a few
  seconds, without refreshing.
* The ticket shows the order number, the **table number**, the waiter, every dish with quantity
  and **portion** (Half or Full), and a timer.

**Also check**
* Can the chefs read it from where they stand?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-C2. Move the ticket through the kitchen

**Steps**
1. Tap **Start**, then **Bump Ready**, then **Serve**. Try **Recall** once to move it back a step.

**Expected**
* The ticket moves column by column. The **Orders** screen at the till follows it (In Kitchen,
  Ready, Served) without anyone touching the till.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section D: Settling the bill

### UAT-D1. Check the bill

**Who:** cashier.

**Steps**
1. Select the busy table and tap **Settle Table**. Tap **View Receipt**, read it, close it.

**Expected**
* Each order on the table with Total, Paid and Due.
* The bill if paid in cash (16%) and by card (5%), side by side. Check both by hand.
* The receipt: restaurant name once, address, order number, date and time, table, every dish
  with portion, subtotal, tax, total, and the footer.

**Also check**
* What is missing from the receipt compared with your current bills (NTN, PRA number, phone,
  FBR/PRA invoice number, QR code)?

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-D2. Take a cash payment

**Steps**
1. Payment mode **Cash**. Enter the amount handed over (more than the bill) and post the payment.

**Expected**
* "Cash payment recorded. Change: Rs. [amount]" in whole rupees. Due Rs 0, **Session Fully
  Paid**.
* If the food was already served, the order completes and the table turns green straight away.
* If the guests paid before the food came, the table **stays red** until the kitchen taps
  **Serve**, then turns green by itself.
* The dishes' ingredients leave stock (checked in Section I).

**Also check**
* On other tables: pay by **Card** (5% bill), **Split** cash and card, and give a discount.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section E: Cash drawer

### UAT-E1. Open the drawer at the start of the day

**Who:** cashier or owner.

**Steps**
1. Tap **Drawer** in the top bar (it is on every till screen).
2. Count the cash you are starting with, enter it as the **Opening float**, tap **Open drawer**.

**Expected**
* "Drawer opened, Float Rs. [amount]." A green dot appears on the Drawer icon.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-E2. Close the drawer at the end of the day

**Steps**
1. Take a cash payment and record a cash expense for today first (UAT-J3), so the figures move.
2. Tap **Drawer**. Read the breakdown.
3. Enter the cash you counted. Optionally write a note (for example the reason for a
   difference) and attach a photo or PDF (for example a slip).
4. Tap **Close drawer**, then **Yes, close drawer**.

**Expected**
* The breakdown: Opening float, + Cash sales, - Cash refunds, - Cash expenses today, + Other cash
  income today, = **Should be in the drawer**. Check it by hand.
* As you type the count, it shows **Over by**, **Short by** or **Exact**, before you commit.
* After closing: expected, counted and over/short, your note, and how many files were attached.
  The dot on the Drawer icon turns grey.
* The same figures, note and files appear on that day's **Z-Report** (UAT-H2).

**Also check**
* Next morning, open the drawer again with the new float.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section F: Takeaway and Call Center

### UAT-F1. A takeaway order

**Steps**
1. From the channel screen tap **Takeaway**. Add two dishes and complete the order and payment.

**Expected**
* The order gets a number, reaches the kitchen, and shows under Orders.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-F2. A phone order

**Steps**
1. Tap **Call Center**. Search a phone number; if it is new, add the customer with an address.
2. Add dishes and place the order. Search the same number again.

**Expected**
* The second search finds the customer with their address and past orders, and can repeat an
  order.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section G: Orders screen

### UAT-G1. Find an order

**Steps**
1. Tap **Orders** in the top bar. Use the tabs **All**, **Active**, **In Kitchen**, **Ready**,
   **Completed**.

**Expected**
* Each card: order number, channel, status, items, total, table, how long ago.
* A paid and served order is under **Completed**. An unpaid served table offers **Settle Bill**,
  never Complete.
* **Void** asks for a manager and a reason.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: older sample orders are numbered "DN-0001" and so on; new orders use the date
> format. The sample ones will be removed before go-live.

---

## Section H: Owner's back office

### UAT-H1. Dashboard

**Who:** owner. **Steps:** tap **Admin** in the top bar.

**Expected**
* **Today's Revenue**, **Orders Today**, **Avg Order Value**, each compared with yesterday up to
  the same time; **Table Utilization** as a percentage of busy tables.
* **Live feed**: tables placing orders and settling bills, updating every few seconds.
* **Hourly Sales** chart, **Live Operations** per order type, **Top 5 Items** with photos.
* "Today" is Pakistan's day from midnight.
* The left menu is grouped: Sales & Reports, Inventory, Purchasing, Settings.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: Live Operations shows an "Online" card; you have no online ordering, so it will
> stay at 0.

### UAT-H2. Z-Report (daily settlement)

**Steps**
1. **Sales & Reports > Z-Report**. Pick today, then yesterday. Tap **Print** once.

**Expected**
* Settled orders, refunds, net revenue, tax, discounts; sales by channel and by payment method.
* **Cash Position**: cash taken, refunds, cash paid out (each cash expense listed), other cash
  income, **net cash for the day**, and **cash in hand** at the start and end of the day (from
  your opening cash, UAT-J4).
* One block per **drawer**: times, float, expected, counted, over/short, note and files.
* **Inventory used** that day and **stock left at close**, with low stock flagged.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-H3. Reports

**Steps**
1. **Sales & Reports > Reports**. Try Today, Yesterday, This Week, This Month.

**Expected**
* Each figure compared with the same stretch of the previous period (a part-week against the same
  days of last week).
* Top 10 and Bottom 5 items with photos, hourly revenue over the whole range, waiter
  performance, and orders by table size.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section I: Inventory and recipes

### UAT-I1. Stock

**Steps**
1. **Inventory > Stock**. Search for "chicken". Note one ingredient's quantity, place and pay an
   order containing a dish that uses it, then check again.

**Expected**
* Every ingredient with a photo, quantity, unit and reorder level; low stock flagged.
* The quantity drops by exactly the recipe amount once the order is paid and served.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-I2. Opening stock (go-live count)

**Steps**
1. **Inventory > Stock > Opening Stock**. Change two figures and save.

**Expected**
* Every ingredient on one screen with the system figure; only the rows you change are saved.
  Saving the same figures again changes nothing.

**Also check**
* Do this once on the morning you go live, before the first sale.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-I3. Recipes and portions

**Steps**
1. **Inventory > Recipes**. Open Chicken Karahi.

**Expected**
* The recipe lists the bought ingredients with quantities and cost.
* **Portions and add-ons** below it: Half (nothing extra, the base recipe) and Full (what it
  adds, and the extra cost).

**Also check**
* Are the quantities right for your kitchen? Tell us the real ones for your best sellers.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section J: Purchasing and money

### UAT-J1. Suppliers and purchase orders

**Steps**
1. **Purchasing > Suppliers**: open one and read its purchase history.
2. **Purchasing > Purchase Orders**: create a purchase order for two ingredients, send it, then
   **Receive** it.

**Expected**
* Dates read like 24 Sep 2026. Purchase orders and receipts are numbered with today's date.
* Receiving adds exactly the received quantities to stock.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-J2. Other income

**Steps**
1. **Purchasing > Other Income**: add a scrap sale of Rs 500, cash, today.

**Expected**
* It appears in the list and in today's Z-Report cash position, and in the drawer's "Other cash
  income today". A bank receipt does not count as cash.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

### UAT-J3. Expenses

**Steps**
1. **Purchasing > Expenses > Add expense**. Payee "Electrician", Rs 200, status **Paid**. Try to
   save without choosing **Paid by**, then choose **Cash** and save.

**Expected**
* The date is today (also after midnight).
* A paid expense cannot be saved until **Paid by** (Cash, Bank or Cheque) is chosen.
* A cash expense shows in the drawer's "Cash expenses today" and the Z-Report.
* An invoice photo or PDF can be attached to an expense.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

> Known today: the Expenses page says "VAT" in two places; it will say GST like the rest of the
> system.

### UAT-J4. Opening cash in hand

**Steps**
1. At the top of **Purchasing > Other Income**, set the cash the business held on your first day
   (till, safe and petty cash).

**Expected**
* The Z-Report carries it forward day by day as cash in hand at the start and end of each day.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section K: Staff and settings

### UAT-K1. Staff

**Steps**
1. **Settings > Staff**. Check the waiters and roles; add one test waiter with a PIN, then log in
   with that PIN.

**Expected**
* The new waiter can log in with that PIN and take orders.

**Also check**
* Tap **Admin** as the waiter. Tell us exactly what a waiter and a cashier should and should not
  be able to open.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

## Section L: On a phone

### UAT-L1. The main screens on a phone

**Device:** an ordinary Android phone in Chrome, upright and sideways.

**Steps**
1. Log in. Open Dine-In, add a dish, open the Drawer, open Admin > Dashboard and the Z-Report.

**Expected**
* No sideways scrolling; nothing cut off; the top bar fits (on a phone the Drawer button shows as
  an icon).
* Buttons are easy to tap; dialogs such as the drawer scroll when they are taller than the screen.

**Result:** Pass / Fail / Note  **Your notes:** ______________________

---

**Thank you.** Send the completed guide, with your notes, to Sitara Infotech. Every Fail and Note
is logged and answered before go-live.
