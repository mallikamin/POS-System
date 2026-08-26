Scope of Work: Web-Based POS, Inventory & Procurement Management System

Prepared by: FZ LLC
Client Representative: Martin Zubeldia
Requirement Discussion: 24 August 2026
Document Purpose: Scope Confirmation & MVP Planning

# 1. Project Overview

We need a simple, customized, web-based POS, Inventory and Procurement Management System. The objective is to avoid unnecessary functionality found in existing POS platforms and provide a streamlined solution focused on sales, inventory consumption, procurement, production/recipes, stock transfers and accurate profitability reporting.

We need the system to consist primarily of two interconnected operational modules: Point of Sale (POS) and Inventory & Procurement. Sales made through the POS will automatically affect the corresponding inventory at the relevant location.

# 2. Point of Sale (POS) Module

We need the POS to provide a simple interface for processing customer orders:

* • Menu-based POS interface for punching customer orders.
* • Products/items and applicable modifiers.
* • Each menu item and modifier linked to corresponding inventory ingredients/items.
* • Automatic inventory deduction upon sale.
* • Location-based sales and stock deduction.
* • Capacity to issue invoices as tickets or as A4 invoices with a proper tax invoice template, including mandatory fields for VAT and the full company name.
* • Capacity to issue quotations directly from the back office.
* • For B2C invoices, minimum CRM capability supporting name, phone, and address as non-mandatory fields.
* • Different sales/order channels recorded for profitability calculations.

We need a focused POS rather than a large CRM or marketing platform.

# 3. Inventory Management

* • Item and ingredient master.
* • Current stock quantity and location-wise inventory.
* • Automatic stock deduction from sales.
* • Automatic stock addition upon receiving purchases.
* • Authorized manual inventory adjustments.
* • Low-stock identification/alerts.
* • Stock movement/history.
* • Inventory transfers between locations.
* • Tracking of received, produced and transferred inventory.

# 4. Recipe, Sub-Recipe & Production Management

We need the system to support inventory conversion rather than treating every inventory item only as a purchased finished product.

* • Example workflow: Raw Ingredients -> Sub-Recipe -> Intermediate Product -> Final Product
* • Define raw materials and ingredients.
* • Create recipes and sub-recipes.
* • Support multiple recipe/production layers.
* • Convert raw materials into produced inventory.
* • Automatically deduct ingredients consumed during production.
* • Add produced quantity to inventory.
* • Link final POS products with recipes/sub-recipes.
* • Maintain quantities for both purchased and internally produced items.

# 5. Supplier & Procurement Management

## 5.1 Supplier Management

* • Supplier master/profile and contact information.
* • Items associated with each supplier.
* • Supplier purchase history.

## 5.2 Purchase Order Workflow

Select Location -> Select Supplier -> Select Items -> Create PO -> Send PO -> Receive Goods -> Update Inventory

* • Create purchase orders by location and supplier.
* • Select required items and quantities.
* • Generate a purchase order and send it to the supplier by email.
* • Maintain PO status.
* • Receive goods against a purchase order.
* • Update stock after goods receipt.
* • AI-assisted purchase order automation where you can specify target production amounts for the week, and the AI suggests what and what to order based on existing inventory and recipes.

# 6. OCR-Based Goods Receiving

To reduce manual data entry during receiving, we need the system to incorporate OCR-assisted document/item receiving.

Upload/Scan Receiving Document -> OCR Extraction -> User Review -> Correction if Required -> Confirm Receipt -> Update Inventory

* • Upload an image/document when receiving stock.
* • Extract relevant information through OCR.
* • Present extracted information for verification.
* • Allow manual corrections before confirmation.
* • Confirm received quantities and update inventory.

# 7. Multi-Location Management

* • Location-specific inventory and POS transactions.
* • Purchase orders and goods receiving by location.
* • Stock transfers between locations.
* • Sales and inventory reporting by location.
* • Automatic deduction from the location where the sale occurs.

# 8. Sales Channel & Net Profitability Reporting

We need a key customized requirement to calculate actual profitability according to the sales channel rather than simply calculating Selling Price - Product Cost.

* • Example: Deliveroo Net Profit = Selling Price - Product Cost - Deliveroo Commission
* • Example: WhatsApp/Direct Net Profit = Selling Price - Product Cost - Applicable Channel/Payment Commission

We need the system to allow applicable commission percentages/costs to be associated with different sales channels and use these costs when calculating profitability.

# 9. Dashboard & Reports

Reporting will intentionally remain simple and operationally focused.

* • Daily and monthly revenue.
* • Sales by location and sales channel.
* • Product/item sales and most sold items.
* • Most consumed items inventory report.
* • Modifier most sold report.
* • Inventory/stock position and low-stock items.
* • Purchase/receiving history and stock transfer history.
* • Product cost and channel commissions.
* • Net profit after product cost and applicable commission.

Final report formats and exact KPIs will be confirmed during the MVP review.

# 10. User & Access Management

We need the application to include secure user authentication and basic role-based access. Indicative roles may include Administrator, POS/User, Inventory/Procurement User, and Management/Reporting User. Final permissions will be confirmed during the MVP stage.

# 11. Proposed System Workflow

* • Procurement: Low Stock / Requirement -> Purchase Order -> Supplier -> Goods Received -> OCR Verification -> Inventory Updated
* • Production: Raw Materials -> Recipe/Sub-Recipe Production -> Raw Stock Deducted -> Produced Stock Added
* • Sales: POS Order -> Product/Modifier Selected -> Sale Completed -> Relevant Ingredients/Inventory Deducted
* • Profitability: Sale -> Identify Sales Channel -> Deduct Product Cost -> Deduct Channel Commission -> Calculate Net Profit
* • Stock Transfer: Source Location -> Destination Location -> Items/Quantity -> Transfer -> Update Both Locations