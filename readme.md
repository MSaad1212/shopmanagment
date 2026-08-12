# Business Management System — Full Specification Document

**Prepared for:** Build via Antigravity (AI coding agent), module by module
**Audience note:** Written in plain language for a non-technical owner, but detailed enough for a developer/agent to build directly from it.

---

## 1. What This System Does (Plain Summary)

This is a web-based system to run your business's daily business:

- Track every gas kit/item in stock (how many you have, cost, selling price)
- Record purchases from suppliers and sales to customers
- Record **returns** — both when you return goods to a supplier, and when a customer returns goods to you
- Keep a running **ledger** (a running account) for every supplier and every customer, showing what you owe them or what they owe you (credit/debit)
- Print professional invoices, receipts, and reports
- Restrict access with a login page, so only authorized staff can use it

Think of it as replacing your notebooks/registers with a proper computer system that never loses data, calculates totals automatically, and lets you search history in seconds.

---

## 2. Technology Stack (What It's Built With)

| Layer | Choice | Why |
|---|---|---|
| Backend (brains of the app) | Python + FastAPI | Fast, reliable, easy to maintain |
| Database (where data is stored) | MySQL | Solid, free, widely supported, handles financial data safely |
| Frontend (what you see/click) | Jinja2 templates + HTMX | Simple web pages, fast to build, no heavy app needed |
| PDF/Print formats | WeasyPrint | Generates clean printable invoices/reports as PDF |
| Development | Local (your own computer) — build and test here first | No cost, fast to test, no internet needed while building |
| Hosting (later, after testing) | Low-cost VPS (Hetzner or DigitalOcean) | You own your data, low monthly cost (~$5-10/month) |
| Deployment | Run directly on your machine/VPS (no Docker/containers) | Simpler to set up and manage for a single-shop system |
| Access | Web browser (desktop, tablet, or phone) | No installation needed on shop computers |

---

## 3. User Roles & Login Module

### 3.1 Roles
Since you're the only person running the shop, the system needs just **one role: Admin (Owner)** — full access to everything, including sales, purchases, returns, deleting records, and reports.

There's no separate Cashier/Staff role for now. The login page and user table are still built (so the shop's data stays private and secure, and so you can add a staff account later with a couple of clicks if you ever hire help) — but only one Admin account needs to exist on day one.

### 3.2 Login Page — Fields & Behavior
- Username
- Password (hidden/masked)
- "Remember me" checkbox
- Login button
- Forgot password → resets via Admin (no email needed initially, keep it simple)

### 3.3 Rules
- Passwords stored securely (hashed, never in plain text)
- After 5 failed attempts, lock for 10 minutes (basic security)
- Every action in the system (sale, return, edit) is tagged with **which user did it and when** — this is called an audit trail, and it protects you if there's ever a dispute about who changed what.
- Session expires after inactivity (e.g., 2 hours) and requires re-login

### 3.4 User Management Page (Admin only)
- View/edit your own Admin profile and password
- The ability to add another user (with role selection) should still exist in the system for future use, but you won't need to use it unless you bring on staff later
- Deactivate a user (don't delete, so history stays intact) — for future use

---

## 4. Stock / Inventory Module

This is the heart of the system — everything you have for sale.

### 4.1 Item Record — Fields
| Field | Example | Notes |
|---|---|---|
| Item Code | MT-0001 | Auto-generated, unique |
| Brand | Dunlop, Bridgestone, GT Radial | |
| Size | 175/65 R14 | Standard gas kit size format |
| Pattern/Model | Sport, Eco | |
| Type | Tubeless / Tube-type | |
| Category | Car gas kit, Bike gas kit, Truck gas kit, Tube, Rim, Accessory | You may sell more than just gas kits |
| Purchase Price | Cost price per unit | Used to calculate profit |
| Sale Price | Selling price per unit | |
| Current Stock Quantity | Auto-calculated | Never edited manually — only changes through purchase/sale/return entries |
| Reorder Level | e.g. 5 | System warns you when stock drops below this |
| Unit | Piece | |
| Status | Active / Discontinued | |

### 4.2 How Stock Quantity Changes (Automatic — you never manually type stock numbers)
- **Purchase entry** → stock goes **up**
- **Sale entry** → stock goes **down**
- **Customer return** (they bring goods back) → stock goes **up**
- **Supplier return** (you send goods back) → stock goes **down**
- **Stock adjustment** (rare — for damage, loss, manual correction) → Admin-only, requires a reason note

### 4.3 Stock Pages Needed
1. **Item List** — searchable/filterable table (by brand, size, category, low-stock)
2. **Add/Edit Item** — form with fields above
3. **Stock Ledger per Item** — a history log showing every purchase, sale, and return that affected this specific item's quantity, like a diary for that item
4. **Low Stock Report** — items below reorder level, so you know what to order

---

## 5. Supplier Module

### 5.1 Supplier Record — Fields
- Supplier Code (auto)
- Supplier/Business Name
- Contact Person
- Phone Number
- Address
- Opening Balance (how much you owed/were owed when you started using the system)
- Status (Active/Inactive)

### 5.2 Purchase Transaction (Buying Stock From Supplier)
| Field | Notes |
|---|---|
| Purchase Invoice No. | Auto-generated |
| Date | |
| Supplier | Select from list |
| Items | Multiple rows: item, quantity, purchase price, subtotal |
| Total Amount | Auto-calculated |
| Amount Paid Now | Can be full, partial, or zero (credit purchase) |
| Balance | Total − Paid |
| Payment Method | Cash / Bank Transfer / Cheque |

**What happens automatically:**
- Stock quantity for each item increases
- Supplier ledger gets a new entry (you now owe them, or owe them less if paid)

### 5.3 Supplier Return (You Send Goods Back to Supplier — e.g., defective gas kit)
| Field | Notes |
|---|---|
| Return No. | Auto |
| Date | |
| Supplier | |
| Original Purchase Invoice | Link to which purchase this relates to (optional but recommended) |
| Items Returned | Item, quantity, rate |
| Total Return Value | Auto-calculated |
| Refund Method | Cash refund received / Adjusted against balance owed |

**What happens automatically:**
- Stock quantity decreases
- Supplier ledger gets a credit entry (reduces what you owe them, or increases what they owe you)

### 5.4 Supplier Ledger (Running Account)
A page per supplier showing every transaction in date order:

| Date | Description | Debit | Credit | Balance |
|---|---|---|---|---|
| 1 Aug | Opening Balance | | | Rs. 50,000 (you owe) |
| 3 Aug | Purchase Invoice #12 | Rs. 20,000 | | Rs. 70,000 |
| 5 Aug | Payment Made | | Rs. 30,000 | Rs. 40,000 |
| 8 Aug | Return #4 | | Rs. 5,000 | Rs. 35,000 |

**In plain terms:** Debit = you owe more; Credit = you owe less (or they owe you). This is a standard accounting ledger, automatically maintained — you never calculate it by hand.

### 5.5 Supplier Payment Entry
- Simple form: Supplier, Date, Amount Paid, Method, Note
- Updates the ledger and reduces balance owed

---

## 6. Customer Module

Mirrors the Supplier module exactly, but from the opposite side.

### 6.1 Customer Record — Fields
- Customer Code (auto)
- Customer Name
- Phone Number
- Address
- Vehicle info (optional, useful for a business — e.g., "Corolla 2018")
- Opening Balance
- Status

### 6.2 Sales Transaction (Selling to Customer)
| Field | Notes |
|---|---|
| Sale Invoice No. | Auto |
| Date | |
| Customer | Select from list, or "Walk-in / Cash Customer" if not registered |
| Items | Item, quantity, sale price, subtotal |
| Total Amount | Auto-calculated |
| Amount Received Now | Full / Partial / Zero (credit sale) |
| Balance | Total − Received |
| Payment Method | Cash / Bank / Cheque |

**Automatically:** Stock decreases; customer ledger updated.

### 6.3 Customer Return / Daily Return (Customer Brings Goods Back)
This is your **"daily return"** requirement — handled here.

| Field | Notes |
|---|---|
| Return No. | Auto |
| Date | |
| Customer | |
| Original Sale Invoice | Link (recommended) |
| Items Returned | Item, quantity, rate, reason (defective, wrong size, changed mind) |
| Total Return Value | Auto |
| Refund Method | Cash given back / Adjusted against balance owed |

**Automatically:** Stock increases; customer ledger credited.

### 6.4 Customer Ledger
Same structure as supplier ledger — shows what each customer owes you over time, every sale, payment, and return in one running account.

### 6.5 Customer Payment Receipt
Simple form: Customer, Date, Amount Received, Method, Note.

---

## 7. Daily Returns Dashboard (Your Specific Request)

A dedicated page that shows, for any selected date (defaults to today):
- All supplier returns made that day
- All customer returns received that day
- Total value of returns (in and out)
- Quick filter by item, brand, or reason

This gives you a fast daily snapshot without digging through individual ledgers.

---

## 8. General Ledger / Accounts Overview

A summary page for the whole business (Admin only):

- **Total Receivables** — total amount all customers owe you combined
- **Total Payables** — total amount you owe all suppliers combined
- **Cash/Bank Summary** — money in vs money out for a selected period
- **Daily Cash Book** — every cash transaction for a given day, one list

---

## 9. Reports Module

| Report | Shows |
|---|---|
| Sales Report | Sales by date range, by item, by customer |
| Purchase Report | Purchases by date range, by item, by supplier |
| Returns Report | All returns (supplier + customer) with reasons |
| Stock Valuation Report | Current stock × purchase price = total money tied up in stock |
| Profit Report | Sale price − purchase price, per item/period (Admin only) |
| Outstanding Balances Report | Which customers owe you, which suppliers you owe, sorted highest first |

---

## 10. Print Formats (via WeasyPrint)

- Sales Invoice (with shop name/logo, item table, total, balance due)
- Purchase Invoice
- Return Receipt (customer or supplier)
- Ledger Statement (printable account statement for a supplier or customer, e.g. to hand them or send on request)
- Daily Cash Summary

---

## 11. Database Tables (Plain-Language List for the Developer/Agent)

1. `users` — login accounts and roles
2. `items` — stock catalog
3. `stock_movements` — every single change to stock quantity, with reason and link to source transaction
4. `suppliers`
5. `customers`
6. `purchases` + `purchase_items`
7. `sales` + `sale_items`
8. `supplier_returns` + `supplier_return_items`
9. `customer_returns` + `customer_return_items`
10. `supplier_ledger` — every debit/credit entry per supplier
11. `customer_ledger` — every debit/credit entry per customer
12. `payments_made` (to suppliers)
13. `payments_received` (from customers)
14. `audit_log` — who did what, when

---

## 12. Suggested Build Order (Phases for Antigravity)

Build and test one module fully before moving to the next — this keeps things simple and lets you start using parts of the system early.

1. **Phase 1 — Foundation:** Database setup, login page, user roles, basic navigation shell
2. **Phase 2 — Stock Module:** Item catalog, add/edit items, stock list, low-stock report
3. **Phase 3 — Supplier Module:** Supplier records, purchase entry, supplier ledger, supplier payments
4. **Phase 4 — Customer Module:** Customer records, sales entry, customer ledger, customer payments
5. **Phase 5 — Returns Module:** Supplier returns, customer returns, daily returns dashboard
6. **Phase 6 — Ledger & Reports:** General ledger overview, all reports listed in Section 9
7. **Phase 7 — Print Formats:** All PDF templates in Section 10
8. **Phase 8 — Polish:** Search, filters, dashboard homepage with key numbers (today's sales, today's returns, low stock alerts, outstanding balances)

---




