# PRD — Fatin Penhores Pawn System

**Last updated:** 2026-02 (Iteration 17)

## Original Problem Statement
Pawn shop management system for Fatin Penhores (Dili, Timor-Leste). Modules: Dashboard, Client Management, Pawn Item Management (separate tables for Car, Motorcycle, Electronic), Pawn Contract Module (CTR-YYYY-#### numbering, 10/15% interest, statuses), Payment Module (full/partial/interest-only), Auction Module, Reports, PDF/Print, User Account/Admin Module, Public Website.

Flow: Client → Pawn Item → Contract → Payment → Redeem / Reactivate / Auction → Invoice → Report.

## User Personas
- **Admin** — full access including users, settings, audit log, deletions.
- **Staff** — clients, items, contracts, payments, auctions (no user mgmt, no settings).
- **Cashier** — payments only; read access to clients/contracts/items.
- **Public visitor** — public site, contact form, auction listings.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). JWT in httpOnly cookies. PDFs via ReportLab. Object storage via Emergent integrations. WhatsApp Cloud API (Meta).
- **Frontend**: React 19 + react-router v7 + Shadcn/UI + Tailwind + Recharts. Bilingual EN/TET.

## Implemented (Iter 1 + Iter 2 + Iter 3)
### Core (Iter 1)
- JWT auth, admin seed, role-based access.
- Clients CRUD with TL address taxonomy.
- Three separate item collections (cars / motorcycles / electronics).
- Contracts with CTR-YYYY-#### auto-number, status recomputation.
- Payments with RCP-YYYY-#### receipts.
- Auction lifecycle. Reports + CSV export. PDFs.
- Public site (Home, Auction, Warehouse, About, Contact).

### Operations (Iter 2)
- Settings page with bilingual T&C templates, WhatsApp credentials, reminder window.
- Default interest by item type (Car 10 / Motorcycle 15 / Electronic 15) with manual override.
- Richer contract PDF.
- Object storage uploads for photos + documents.
- Recharts dashboard (monthly trends + overdue by type).
- **Cashier role** (payments-only RBAC).
- Audit log on key mutations.
- WhatsApp Cloud API (Meta direct) — mocked when token absent.
- Language toggle EN ↔ TET.

### Compliance & Business Logic (Iter 3 — 2026-02)
- **Client picture upload** (storage_path) + "View Details" action with bilingual modal showing photo, profile, contracts, payment history.
- **Drivers License** added to id_type (BI / Electoral / Passport / Drivers License).
- **Multi-pawn per client** — backend already supports any number of concurrent contracts per client.
- Item fields: **market_value** added; **manufacture_year** (renamed from year) on all 3 item types.
- **Contract max term 62 days** (~2 months) enforced on create AND on reactivate.
- **Reactivate overdue contracts** — new POST /api/contracts/{id}/reactivate; clears penalty; status → active; new due date in future, capped 62 days from today.
- **Principal vs Interest split** in payment math: partial payments reduce principal first; interest_only payments reduce interest first; full pays interest then principal. Minimum 1 interest period always charged.
- **10% Penalty** of original loan amount auto-applied when contract is overdue (excludes interest); shown in dedicated Contracts table column.
- **Client payment history** endpoint GET /api/clients/{id}/payments aggregated across every contract.
- **Tetum contract PDF** matching the official template with 14 articles, header band, summary box, item detail table, signature block.

## Implemented (Iter 8 — 2026-02)
- **Finance/Invoices PDF exports** (per user request "add pdf in finance module in each category"):
  - `GET /api/finance/summary/export/pdf` — branded Finance Summary PDF (KPIs + cash flow + expenses by category).
  - `GET /api/finance/capital-sources/export/pdf` — Capital Sources register with totals (principal/repaid/outstanding).
  - `GET /api/finance/expenses/export/pdf?category=&month=&year=` — Operating Expenses PDF with optional per-category filter (Salary/Maintenance/Utilities/etc.) and date filters; includes a by-category summary when no filter is set.
  - `GET /api/invoices/export/pdf` — Invoice Register (all invoices).
  - `GET /api/invoices/{id}/pdf` — Single Invoice PDF (auto-generated when an auction is marked sold).
- **Auctions sold flow now idempotent** — re-posting `/auctions/{aid}/sold` returns the existing invoice rather than minting duplicates.
- **Frontend**: "Summary PDF" button in Finance header, "Export PDF" buttons on Capital Sources & Expenses tabs, category-filter dropdown in Expenses tab, new "Invoices" tab listing all invoices with per-row PDF buttons + bulk export. Auctions page shows an invoice download link on sold rows.
- **EN/TET i18n** keys added for invoice/finance terms.

## Implemented (Iter 9 — 2026-02)
- **Pezadu (Heavy Equipment) category** — backend `pezadus` collection + frontend tab with subcategories Forklift / Tractor / Loader / Heavy Duty Truck. Default interest rate configurable in Settings.
- **WhatsApp Meta API — real integration** with **Fernet encryption** (`/app/backend/encryption.py`) for token at rest. Settings UI shows masked token preview + connected badge. `POST /api/whatsapp/test` validates creds against Meta Graph API.
- **Public Warehouse password gate** — admin sets `warehouse_password` in Settings; visitors must unlock via `POST /api/public/warehouse-unlock` to view `/public/warehouse`. Status endpoint reports locked/unlocked.
- **Automated daily backups** — `apscheduler` background job at 02:00 UTC, keeps last 7 snapshots in `/app/backups`. Settings UI lists existing backups, lets admin manually trigger `/admin/backups/generate` and `/admin/backups/generate-project` (full source-code zip), and download with path-traversal protection.
- **Public website redesign** — navy header + yellow active links + Services, Simulasaun, FAQ pages.
- **UI polish** — color-coded Item tabs (Cars/Motos/Electronics/Pezadu), compact non-wrapping tables across Contracts/Clients/Payments/Auctions, shortened CT-2026-N contract display, universal red PDF download buttons.
- **Bugfix**: backups subprocess now uses `sys.executable` (was bare `python3` → resolved to system python without `motor` → 500). Verified zips generate and download correctly.

## Implemented (Iter 10 — 2026-02)
- **Item name + machine_number** — Car / Motorcycle / Pezadu all gained `name` (e.g., "Toyota Hilux 2026 Black") and `machine_number` (engine no., distinct from chassis). Visible in forms + tables.
- **Pre-Auction workflow** — Contracts 1-10 days overdue are tolerated and listed in a Pre-Auction amber card. Contracts > 10 days overdue auto-transition to `auction_ready` status. New computed fields on every contract response: `days_overdue` (int), `penalty_paid`, `penalty_full`.
- **Overdue Payments** — New Payments tab + dedicated dialog with 3 modes:
  - `overdue_full` → covers Penalty → Interest → Principal (full close-out; status → `redeemed`)
  - `overdue_interest_pen` → covers Penalty → Interest (principal stays open)
  - `overdue_penalty_only` → records only the 10% penalty payment (so the cash is captured in the books)
- **Client Payment Summary** — Inside Client View Details modal, a 5-card grid (Total Paid / Full / Partial / Interest / Penalty) totals across ALL contracts.
- **Finance — Capital Sources rate/term selectors** — Rate dropdown 2-10%, Term dropdown 6-12 months, live interest preview (`principal × rate × term-factor`).
- **Finance — Loan Calculator tab** — Standalone simulator with rate (2-10%), term (6-12), monthly/yearly period. Live total interest, total repayment, monthly payment, 12-month schedule.
- **Auction Sold split** — `AuctionSoldIn.interest_fee` optional. When provided, `cash_portion = sold_price − interest_fee`. When omitted, auto-computed from contract's outstanding interest + penalty. `interest_fee` flows to `net_profit` in `/finance/summary`; `sold_price + tax` flows to `cash_on_hand`. **Buyer invoice PDF intentionally shows only Subtotal/Tax/Total — no interest line.** Internal accounting stored as `_internal_interest_fee` / `_internal_cash_portion` on the invoice doc.
- **Bugfix (testing agent)**: `PezaduIn` model was missing `name` + `machine_number` (Pydantic v2 'ignore' silently dropped them on POST). Added both with empty defaults.

## Implemented (Iter 13 — 2026-02)
- **Per-user Module Access (RBAC v2)** — admin can now tick which modules each user can access when creating/editing them.
  - Backend: `UserOut` / `auth/me` / `auth/login` all expose `allowed_modules: List[str]`. New constants `ALL_MODULES` (11 modules) + `ROLE_DEFAULT_MODULES` ({admin: all, staff: 7, cashier: dashboard+payments}). New `require_module(name)` dependency factory; applied to list endpoints for clients, items, contracts, payments, auctions, dashboard, finance, reports/v2. Admin role always bypasses (returns immediately). New GET `/api/users/modules` catalog endpoint (admin-only). PATCH `/api/users/{id}` supports `allowed_modules`. POST creating an admin auto-locks to `ALL_MODULES`. Bad module names are silently filtered out.
  - **Migration**: on boot, every existing user document without `allowed_modules` is backfilled with the role default (admin → all 11, staff → 7, cashier → [dashboard, payments]).
  - Frontend Users page (full rewrite): Module Access checkbox grid (11 items, 3 columns) + 4 preset buttons (Staff preset / Cashier preset / All / None). Role dropdown — selecting admin auto-locks all 11 checkboxes and disables them + the preset buttons. Edit dialog (PATCH) pre-fills email (disabled), name, role, current modules. Users list table now shows a Modules column with badge pills per user (admins show "All modules").
  - Frontend Sidebar (`AdminLayout`): nav items are filtered by `user.allowed_modules`. A cashier with only `[dashboard, payments]` sees only those 2 nav links. Admin always sees all 11.

## Implemented (Iter 14 — 2026-02) — P2 polish batch
- **Color-coded Reports tabs** — each of the 7 tabs has a distinct accent color when active (navy / green / terracotta / amber / violet / teal / sage) plus a tinted background when inactive.
- **Shortened document numbers everywhere** — `RCP-2026-0042 → RC-2026-42`, `INV-2026-0015 → INV-2026-15`, `CTR-2026-0112 → CT-2026-112`. Helper: `/app/frontend/src/lib/docNumbers.js`. Full number preserved in `title` attr for hover. Applied across Payments, Clients (payment history modal), Finance Invoices tab, Auctions invoice badge.
- **Photo thumbnails in Items table** — new leftmost "Photo" column (40×40). Renders clickable thumbnail that opens full image in new tab, or dashed placeholder square when no `photo_url`.
- **Public Auction page with password gate** (`/auction`) — locked orange card requires the visitor password. **Shares the existing `warehouse_password`** so one visitor pass unlocks both `/warehouse` and `/auction` (token via `sessionStorage['fp_warehouse_token']`). Backend `/api/public/auction-items` enforces 401 without `unlock_token` when password is set. New `/api/public/auction-status` endpoint. Frontend: colored category chips (navy/terracotta/green/amber), filter row, "Lock" re-lock button.
- **Client-side route guard** — new `ModuleGuard` wraps every admin route. When a non-admin user navigates to a forbidden module they see (a) a red 403 "Access denied" panel with module name + Back to Dashboard button, (b) a sonner toast.error, (c) auto-redirect to `/dashboard` after 2.5s. Admins always bypass.
- **Pezadu filter in Reports → Inventory** — verified pre-existing.

## Implemented (Iter 16 — 2026-02)
- **Loan Disbursement auto-record** — creating a contract now inserts a `Payment` with `type="disbursement"`, `amount=loan_amount`, `date=contract_date`, `notes="Loan disbursed to client at contract signing"`. Appears in client payment history + Finance client_payments filter excludes it (loans_disbursed already reflects the cash-out, prevents double count). `_recompute_contract_status` skips `type="disbursement"` so paid_amount stays 0.
- **"Loan Disbursement Receipt" PDF** — same `/api/payments/{pid}/pdf` endpoint auto-adapts when `payment.type=="disbursement"`: title becomes "Resibu Entrega Empréstimu · Loan Disbursement Receipt"; box switches from repayment layout (Principal/Interest Remaining, Penalty) to disbursement layout (Loan Amount, Amount Received by Client, Interest Rate at maturity, Contract Start/Due). Client signs this on receiving the loan.
- **Frontend Payments — 3rd tab "Disbursements"** — blue-tinted table showing only disbursement transactions with a blue badge (`bg-blue-100 text-blue-900 border-blue-300`). Regular Payments tab now excludes disbursements.
- **Contract PDF — 2 new clauses in Artigu 4º (Prazu Kontratu)**:
  - "Kontratu liu loron 1 konsidera fulan 1" — contract past day 1 counts as 1 full month of interest.
  - "Tolerasia 10 dias — wainhira liu loron 10, kompania sei halo leilaun ka faan sasán penhor (kareta, motor, pezadu)." — 10-day tolerance then auction.

## Implemented (Iter 17 — 2026-02)
- **Backend refactor phase 1**: extracted shared code to `/app/backend/deps.py` (~150 lines): DB client, ALL_MODULES, ROLE_DEFAULT_MODULES, COLLECTION_MAP, `get_current_user`, `require_admin`, `require_module`, `require_roles`, `require_not_cashier`, `write_audit`, `utcnow_iso`, `new_id`, logger. `server.py` now imports from `deps` and shrunk from 2633 → ~2570 lines. All API paths and behavior unchanged.
- **Daily WhatsApp overdue reminders** — new `/app/backend/reminders.py` runs at **00:00 UTC = 09:00 Timor (UTC+9)** via APScheduler CronTrigger. Targets contracts overdue by exactly 7 or 9 days. Sends EN/TET WhatsApp messages via existing `wapp.send_text`. Duplicate prevention via `db.reminder_log` (contract_id + day_bucket + date). UTC-safe date math (`datetime.now(timezone.utc).date()`) so scheduler-timezone drift can't cause double-sends.
- New backend endpoints: `GET /api/reminders/status`, `POST /api/reminders/run` (manual trigger), `GET /api/reminders/logs` (last 90 days, capped at 500 rows) — all admin-only.
- `SettingsIn.reminders_enabled` master toggle (default `True`). When off, run returns `{disabled: True, scanned: 0}`.
- **Settings UI**: new `RemindersCard` between WhatsApp Config and Backups — Bell icon + title + schedule, "Run now" outline button, on/off toggle (accent-amber), 4 stat tiles (Last run / Next run / Sent / Skipped-Errors), dedup explanation footer.

## Implemented (Iter 18 — 2026-02)
- **Payment receipt PDF now includes the Pawn Item block** — Type, Category, Name/Model, Brand, Year, Color, Machine No., Chassis, Plate, Market Value, and optional free-text Description. Warm cream background (#F5F1EA) to visually differentiate from the money box. Applies to BOTH disbursement AND regular repayment receipts.
- **Signature line auto-prints the client's full_name** in bold navy on the left, "Fatin Penhores" on the right, with "Client Signature" / "Authorized Officer" labels below. Client signs next to their own printed name (mirrors passport / notary form UX).
- **Orphan-safe**: if the pawn item was deleted, the receipt still renders cleanly and simply omits the Pawn Item block. Explicit truthiness check (`item and (item.brand or item.name or item.model)`) prevents empty placeholders.

## Test Coverage (cumulative)
- Iter18: **9/9 backend PASS** (Pawn Item block on disbursement + regular payment, signature name on both, orphan safety, free-text description round-trip). Regression: **34/34 iter16+17 PASS**.
- Iter17 (refactor + reminders): 27/27 PASS.
- Iter16 (disbursement + Article 4): 7/7 PASS.
- Iter15 (Contracts overflow): 8/8 PASS.
- Iter14 (P2 polish batch): 46/46 backend + 14/14 frontend PASS.

## Test Coverage (Iter 14)
- Backend: **290/290 PASS** (244 prior + 7 new iter14 auction-gate + 24 iter13 regression + 15 iter10 regression rerun).
- Frontend Playwright iter14: **14/14 PASS** (all bullets in the spec: reports colors, RC/CT/INV short numbers + hover full, photo column, pezadu filter, auction gate + unlock + colored grid + filters + lock-again, sessionStorage sharing, ModuleGuard on 9 forbidden routes for cashier + admin bypass on all routes).

## Test Coverage (Iter 10-13)
- Iter13 (module access RBAC v2): 24+15 PASS.
- Iter12 (items table layout): 15+6 PASS.
- Iter10 (6 new features): 15 PASS.
- Frontend spot-check: login → dashboard → items (4 tabs incl. Heavy Equipment) → contracts (CT-2026 short numbers + red PDF buttons) → settings (WhatsApp + Backups + Warehouse password) → finance (KPIs + charts + 3 tabs) → public Warehouse password gate.

## Test Coverage (Iter 8)
- Backend: **141/141 PASS** (118 prior + 23 new iter8 finance/invoice PDF tests).

## Implemented (Iter 6 — 2026-02)
- **Finance / Treasury module** — admin-only page at `/finance`.
  - **Capital Sources** CRUD (Bank / Company / Personal / Partner / Other) with principal, interest rate, period, start/due date, plus **Repayments** to reduce outstanding balance.
  - **Operating Expenses** CRUD with categories Salary / Maintenance / Travel / Meals / Compensation / Utilities / Rent / Other; cashiers blocked from creating expenses.
  - **Finance Summary** KPIs: cash_on_hand, capital_received/repaid/outstanding, loans_disbursed, client_payments, auction_sales, expenses_total + period, gross_profit, net_profit + expenses_by_category breakdown.
  - **Cash flow BarChart** (inflows green / outflows terracotta) + **Expenses Pie chart** by category.
- **Treasury report** as 7th tab on Reports with Excel + PDF export.
- **WhatsApp number** updated everywhere to `WhatsApp: +670 78372678` (PDF header & footer, Login hero, AdminLayout sidebar, Public footer, Public Contact, Public About).

## Test Coverage (cumulative)
- Backend: **118/118 PASS** (iter1 33 + iter2 22 + iter4-old 22 + iter5 15 + iter6 6 + iter7 20).

## Implemented (Iter 5 — 2026-02)
- **Branded rebrand** from forest green to **company navy** `#1B2D5C / #0F1B3A` (from logo).
- **FP logo image** embedded in: Contract PDF, Receipt PDF, Report PDF (top header), AdminLayout sidebar, PublicLayout header & footer, Login hero.
- **PDF header & footer** show full company details: `FATIN PENHORES UNIPESSOAL, LDA · Caicoli, Dili, Timor-Leste · Tel: 78372678 · fatinpenhores@gmail.com` + copyright `© 2026 Fatin Penhores. All Rights Reserved.` plus a navy left-edge accent bar and silver inner bar matching the logo.
- **Reports**: PDF export button = **red**, Excel button = **green**.
- Public site Contact / About / footer updated with new address, tel, and email.
- Logo bytes are cached in memory after first read to avoid per-request disk IO.

## Test Coverage (cumulative)
- Backend: **98/98 PASS** (iter1 33 + iter2 22 + iter4-old 22 + iter5 15 + iter6 6).
- **Reports module overhauled** to match user mockup: 6 tabs (Active Contracts, Payments, Overdue, Auction, Inventory, Financial), each with 2–4 KPI cards + detail table.
- **Filter bar** (Month / Year / Category / Sub-category) with Filter, Reset, Print, PDF, Excel buttons.
- **Excel export** via openpyxl with branded sheet (KPI block + table). **PDF export** via ReportLab landscape A4.
- **Item `location` field** added to Car / Motorcycle / Electronic (e.g., "Warehouse A / Shop / Off-site"). Listed in Inventory report.
- Inventory KPIs: total_items, total_amount, active_items, overdue_items, by_type{car, motorcycle, electronic}.
- Financial KPIs: total_loan, total_payment, interest_received, total_penalty, profit (= interest_received + total_penalty).

## Test Coverage (cumulative)
- Backend: **92/92 PASS** (iter1 33 + iter2 22 + iter4-old 22 + iter5 15).
- Frontend: 100% — all 6 report tabs, filters, KPI cards (20 across tabs), export links, and item-car-location field verified.

## Prioritized Backlog
### P1 — Stability / Architecture
- **Refactor `server.py`** (now ~2422 lines) into per-domain routers: auth, clients, items, contracts, payments, auctions, invoices, reports, finance, settings, whatsapp, backups, public.
- Daily scheduled WhatsApp reminders (creds wired; cron job pending).
- Performance: move contract status recompute out of report GET into a background job.

### P2 — UI Polish
- Color-coded tabs on Reports page (match Items/Finance).
- Shorten Receipt (RC-2026-N) and Invoice (INV-2026-N) numbers in tables.
- Photo thumbnails (40×40) in admin Items table for quick scanning.
- Auction Public page with colored cards + password gate (like Warehouse).
- Pezadu category filter in Reports → Inventory.
- Recharts ResponsiveContainer width(-1) warning on Dashboard/Finance — wrap charts with `min-h-[300px]`.

### P3 — Enhancements
- Home page hero redesign (full Tetum match: hero copy, category mosaic, 4-step process, testimonials).
- Audit log viewer UI (who changed what & when).
- Email reminders via Resend (needs key).
- Tighten backend Pezadu category validation with `Literal[...]` enum.
- Hard-fail Settings PUT when `WHATSAPP_ENCRYPTION_KEY` missing (avoid silent plaintext storage).

## Credentials
- Admin: `admin@fatinpenhores.tl` / `admin123` (see `/app/memory/test_credentials.md`).
- WhatsApp creds: set via Settings → WhatsApp Configuration. Empty = MOCKED.
