# PRD — Fatin Penhores Pawn System

**Last updated:** 2026-02 (Iteration 32 — WhatsApp Reminders with Rule A Math)

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

## Implemented (Iter 19 — 2026-02)
- **Pre-Auction Actions Column** — new rightmost column on the amber Pre-Auction card in `/contracts`. 4 icon buttons per row for instant action:
  - **WhatsApp** (emerald, `pa-whatsapp-{id}`) — sends Tetum reminder via existing `/api/whatsapp/send`.
  - **Reactivate** (blue, `pa-reactivate-{id}`) — opens the existing dialog to extend the due date.
  - **Move to Auction** (terracotta, `pa-auction-{id}`) — appears **only** on `auction_ready` rows (>10 days overdue); confirms then calls `/api/auctions/move`.
  - **Download PDF** (red, `pa-pdf-{id}`) — opens contract PDF in a new tab.
- Reuses existing helpers (`sendWhatsApp`, `openReactivate`, `moveToAuction`) — zero backend changes.
- Layout verified at 1600×900 EN + 1366×768 EN/TET — no overflow, actions reachable.

## Implemented (Iter 20 — 2026-02) — BREAKING interest model change
- **Monthly interest calculation (Article 4)** — replaces the previous flat one-time rate. Rules:
  - `per_month_interest = loan × rate% / 100`
  - `months_elapsed = max(1, ceil((max(due_date, today) - contract_date) / 30))` — "1 day past = counts as month 1"
  - `interest_amount = per_month_interest × months_elapsed`
  - Overdue contracts have interest that automatically ticks up as time passes
  - New contract response fields: `months_elapsed`, `per_month_interest`, `next_interest_date`
- **"Next Payment" block on receipt PDF** (bilingual Tetum + English) — appears on repayment receipts (not disbursement, not fully-paid):
  - Next payment date
  - Current balance
  - Next month interest (+$X)
  - If unpaid by that date, new total = current + next month
  - Advisory paragraph: "Favor selu iha loron X atu evita interese fulan tan · Please pay by X to avoid another month of interest"
- Repayment box also shows `Interest Rate (per month)` label + `Months Billed So Far` row.
- **Backwards impact**: existing overdue contracts now show higher interest (e.g., 111-day overdue contract that used to show $50 flat now shows $180 for 6 months × $30/mo). Confirmed by user before deployment.

## Test Coverage (cumulative)
- Iter20: **31/31 PASS** — 15 new (Article 4 math on 115 contracts, next_interest_date always strictly future + 30-day aligned, PDF block appears/omits per spec) + 16 iter16+18 regression.
- Iter19 (Pre-Auction actions): 20/20 frontend PASS.
- Iter18 (Pawn Item + auto sign name): 9/9 PASS.
- Iter17 (refactor + reminders): 27/27 PASS.
- Iter14-16: covered.

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

## Iteration 21 (2026-02) — Expense Categories Expansion
- Added 13 new expense categories to Finance → Tabela Despeza:
  `EDTL token Office`, `EDTL token Armazen`, `Mina Trasporte`,
  `Hadia Trasporte Lelaun No Elektróniku`, `Internet Starlink & Telemor`,
  `Pulsa telefone`, `Fo Bónus`, `Broker Trata Dokumentus`, `Gastus Jerál`,
  `Hola Materiál - Armazen 2`, `Trasporte - Armazen 2`,
  `Selu Badain - Armazen 2`, `Tabela ATK FP - Armazen 2`.
- Backend: `EXPENSE_CATEGORY_GROUPS` (ordered, grouped) replaces flat `EXPENSE_CATEGORIES` list. `GET /api/expense-categories` now returns `{groups: [{label, items[]}], flat: [...]}` for backward compatibility.
- Frontend: `Finance.js` now renders the Category `<Select>` with Shadcn `SelectGroup`/`SelectLabel` section headers (Payroll & Bonus / Utilities & Office / Armazen (Warehouse) / Transport & Fuel / Operations / Other). Applies to both the New/Edit dialog and the filter dropdown. Verified via curl + screenshot.
- Regression: `tests/test_iter7_finance.py::TestExpenseCategories::test_list_categories` updated to assert new response shape + all 13 new items present.


## Iteration 22 (2026-02) — Member ID Cards
- Complete card lifecycle for clients: **issue → PDF → renew → revoke → verify**.
- Card format: printable A4 with **front (navy)** + **back (QR)** layout, credit-card size (CR80 85.6×54mm) — cut along dashed border.
- Front: FP logo, "FATIN PENHORES / UNIPESSOAL, LDA" wordmark, "MEMBER ID CARD / Kartaun Membru" ribbon, full name (uppercased), member no., issued/expires dates, photo (from Object Storage) or initials avatar, "Pawn with confidence. Recover with dignity." tagline.
- Back: **QR code** encoding `<PUBLIC_BASE_URL>/verify/<token>`, "SCAN TO VERIFY / Skan atu verifika" (EN/TET), address, WhatsApp/email, fine print + member no.
- Backend endpoints (all `require_not_cashier`, revoke is `require_admin`):
  - `POST /api/clients/{id}/issue-card` — assigns `member_no` (`FP-YYYY-####` yearly seq), status=active, 1-year expiry, secure `member_verify_token` (idempotent — re-issue returns existing values).
  - `POST /api/clients/{id}/renew-card` — extends expiry by 365 days & flips status to active.
  - `POST /api/clients/{id}/revoke-card` (admin-only) — status=revoked.
  - `GET /api/clients/{id}/card-pdf` — returns the printable card PDF.
  - `GET /api/public/verify/{token}` — **PUBLIC (no auth)** — returns `{valid, status, member_no, full_name, photo_url, issued_at, expires_at}` for QR scans.
- Client model gains dynamic fields: `member_no`, `member_status` (`active`/`revoked`), `member_issued_at`, `member_expires_at`, `member_verify_token`.
- Frontend: Member ID Card panel added inside Client details modal (Clients.js) — badge shows Active/Expired/Revoked with color coding, buttons: **PDF**, **Verify Link** (copy to clipboard), **Renew 1 yr**, **Revoke** (admin only, hidden when already revoked).
- New public route: `/verify/:token` (VerifyMember.js) — mobile-friendly card, big status badge (green ✅ / amber ⏰ / red 🚫 / stone ❌), member photo + name + dates. No sensitive data (no ID number, address, contract details).
- New deps: `qrcode==8.2` (Pillow already installed). New env: `PUBLIC_BASE_URL` in `/app/backend/.env` — the domain used in QR codes.
- Audit log: every `issue_card` / `renew_card` / `revoke_card` recorded.
- Tests: `tests/test_iter21_member_cards.py` (10 tests: lifecycle, idempotence, PDF byte-check, public verify happy/bad-token, revoke, renew, RBAC cashier-blocked). **All 10 PASS**.


## Iteration 23 (2026-02) — Mobile Responsive Pass
- **AdminLayout** rewritten with a **slide-out drawer** for `< md` (768px). Desktop unchanged (`hidden md:flex` on the fixed sidebar). New mobile top bar (navy, 56px) shows a hamburger + FP logo + the current page label. Drawer supports body-scroll-lock while open, auto-closes on route change, has an X close button and a tap-outside backdrop. Content area gets `pt-14 md:pt-0` to account for the mobile top bar.
- **Content padding**: All admin pages now use `px-4 py-4 md:px-8 md:py-8` (was `px-8 py-8`) — much more room on phones.
- **Page headers**: Every h1 changed from `text-4xl` to `text-2xl sm:text-3xl md:text-4xl` (Dashboard, Clients, Payments, Reports, Contracts, Items, Auctions, Finance, Users, Settings, Audit Log).
- **Dashboard**: KPI grid now `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` (was forcing 3-col at md, tight at ~800px). Cards use `p-4 md:p-6`, big numbers `text-2xl md:text-3xl` with `break-words`. Charts `h-64 md:h-72`.
- **Reports**: KPI cards default to 2-col on mobile (`grid-cols-2`), numbers `text-xl md:text-3xl` with `break-words`, card padding `p-4 md:p-6`, detail header padding responsive.
- **Finance**: KPI grid 2-col on mobile with `Kpi` component now sized `text-lg md:text-3xl`, `p-4 md:p-6`, `w-5 h-5 md:w-6 md:h-6` icons. Chart containers `h-64 md:h-72`.
- **Radix Tabs (shared)**: TabsList gains `max-w-full overflow-x-auto`, TabsTrigger gains `shrink-0` — tab bars in Payments, Finance, Items now scroll horizontally when they overflow.
- **Radix Dialog (shared)**: Content now `w-[calc(100vw-1.5rem)] max-h-[calc(100vh-2rem)] overflow-y-auto p-4 md:p-6` — dialogs fit any phone, scroll internally when tall, less padding on mobile.
- **Payments**: Overdue-payment "Amount to collect + Date" row uses `flex-wrap` so date picker wraps below.
- Verified via 390×844 (iPhone 12) screenshots on Dashboard, Clients, Payments, Reports, Finance, Items, Auctions, Contracts — hamburger opens/closes drawer, tables horizontally scroll, forms usable, nothing clipped.


## Iteration 24 (2026-02) — Login Page Redesign
- Full professional restyle of `/login`. Left panel (desktop): navy hero with layered treatment (background image at 40% opacity + `bg-gradient-to-br from-[#0B1633]/95 via-[#0F1B3A]/85 to-[#1B2D5C]/70` overlay + inline SVG grain + soft `blur-3xl` accent orbs). Pulsing "Trusted Pawn & Auction House" badge, big hero title, description, and 3 glass trust chips (`10+ Years Serving TL / 24/7 Encrypted Access / USD Same-Day Cash`).
- Right panel: subtle dot-grid pattern background, elevated white card (`rounded-2xl`, backdrop-blur, soft navy shadow), email + password inputs with lucide icons inside (`Mail`, `Lock`), show/hide password toggle (Eye/EyeOff), "Signing in…" state with spinning `Loader2`, and a "Encrypted session · JWT httpOnly cookies" `ShieldCheck` reassurance under the CTA.
- Mobile: hero panel hidden, compact brand centered above the card, everything scales down cleanly. Home back-link + EN/TET toggle pinned to the top corners.
- New data-testids: `login-home-link`, `login-toggle-password`; existing ones preserved (`login-email`, `login-password`, `login-submit`, `login-error`, `login-form`, `login-brand`).


## Iteration 25 (2026-02) — Admin-Only Delete on Payments & Auctions
- Added **`DELETE /api/payments/{pid}`** (admin-only). Deletes the record, then calls `_recompute_contract_status` on the parent contract so the balance/status stays consistent. Writes an audit log entry with the receipt number, amount, type and contract_id for traceability.
- Hardened **`DELETE /api/auctions/{aid}`** (already admin-only): now also reverts the parent contract's status back to `overdue` and unsets `auction_id` when the auction was still `listed`/`auction_ready` — the workflow won't get stuck. Also writes audit log with contract number + prior status.
- **Payments.js**: red trash-outline button appears next to the PDF button on every payment row **only when `user.role === "admin"`**. Confirms with a modal explaining "This will recompute the contract balance. This action is logged." New testids: `payment-delete-{id}`.
- **Auctions.js**: same trash-outline button on every auction row for admin. Confirmation text is adaptive — if `status === "sold"` it warns that the invoice/sale won't be reversed; otherwise it explains the contract will revert to overdue so it can be re-listed or reactivated. New testids: `auction-delete-{id}`.
- Verified via curl: admin delete → 200 & record gone; unauth → 401; cashier → 403 "Admin role required" on both endpoints.


## Iteration 26 (2026-02) — EN↔TET Translation Gap Fix
- **Bug** (user report): "when change to Tetum no translates" — several UI strings stayed in English after selecting TET.
- Added 22 new i18n keys to `/app/frontend/src/lib/i18n.js` (both `en` and `tet` blocks): `login_subtitle`, `login_workspace_body`, `login_years_label`, `login_encrypted_label`, `login_sameday_label`, `login_signing_in`, `login_encrypted_note`, `monthly_trends_sub`, `contracts_past_due`, `treasury`, `finance_cash_on_hand`, `finance_capital_outstanding`, `finance_expenses_lifetime`, `finance_net_profit`, `finance_cash_flow`, `finance_expenses_by_cat`, `detail`, `principal_left`, `interest_left`, `amount_to_collect`, `receipt`.
- Replaced hardcoded English strings with `t()` calls in Login.js (workspace body, 3 trust chip labels, `Signing in…`, subtitle, encrypted note), Dashboard.js (trend/overdue chart subtitles), Finance.js (Treasury eyebrow, 4 KPI labels, cash-flow & expenses-by-category chart titles), Reports.js (Detail eyebrow), Payments.js (Principal/Interest Left, Amount to collect, Receipt column header).
- Removed the two `status` duplicate keys I introduced (kept the pre-existing ones at lines 33 / 326).
- **Testing agent verdict** (report iter_22): **15/15 targeted strings switch correctly**, EN↔TET reversal + localStorage `fp_lang` persistence confirmed. **Bug RESOLVED**.


## Iteration 27 (2026-02) — Services Page Image Fixes
- **Bug** (user report with screenshot): Heavy Equipment ("Garantia Pezadu") card showed a broken image icon on /services; testing agent also caught that the Car ("Karreta") card image was actually a UK "Bond Street" underground sign — not a car.
- Root cause: two hardcoded Unsplash URLs were either 404 (heavy) or crop-mismatched (car).
- Fix:
  - `Services.js` `heavy.img`: was `photo-1581093458791-9d15482442f6` (404) → now `photo-1591768793355-74d04bb6608f` (semi-trailer truck — fits "Kamiaun Pezadu / heavy duty truck").
  - `Services.js` `car.img`: was `photo-1549924231-f129b911e442` (Bond Street sign after auto-crop) → now `photo-1533473359331-0135ef1b58bf` (Ford Expedition SUV — fits "car/SUV/pickup/commercial vehicle").
  - `Home.js` `pez` category tile: updated to the same semi-trailer truck for consistency.
  - Every URL validated first via curl (200 OK) + AI image content check before committing.
- **Testing agent verdict** (report iter_25): **100% pass, 0 issues, retest_needed: false**. All 5 service card images load with contextually appropriate content; Home pez tile regression check also passed.


## Iteration 28 (2026-02) — Member Card PDF Auth Fix
- **Bug** (user report): The Member Card "PDF" button on the Client details modal used raw `window.open(${API_BASE}/clients/${id}/card-pdf, "_blank")`. In some browsers (Chrome new-tab GETs with SameSite httpOnly cookies) the auth cookie was stripped, so the endpoint returned 401 and the tab loaded a JSON error instead of the PDF.
- Fix in `/app/frontend/src/pages/Clients.js` `downloadCardPdf`:
  - Now uses `await api.get('/clients/{id}/card-pdf', { responseType: 'blob' })` — the shared axios instance already has `withCredentials: true` so cookies flow reliably.
  - Wraps the byte stream in a `new Blob([data], { type: 'application/pdf' })`, calls `URL.createObjectURL`, then `window.open(url, "_blank", "noopener,noreferrer")`.
  - Popup-blocker fallback: if `window.open` returns null, we create a hidden `<a href={blobUrl} download="member-card-FP-YYYY-####.pdf">` and click it.
  - Error handling: 401 shows a friendly toast ("Session expired — please sign in again."); other errors surface `response.data.detail`.
  - `URL.revokeObjectURL` cleanup after 60s to release memory.
- Backend endpoint unchanged — still protected via `Depends(require_module('clients'))`.
- **Testing agent verdict** (report iter_26): **100% pass, 0 issues, retest_needed: false**. Verified with a real admin session on `FP-2026-0001`: PDF opens correctly, payments-row PDF anchor still works, 401 toast path also verified.


## Iteration 29 (2026-02) — Client Photo Deployment Fix (Storage-Key URLs + Public Verify)
- **Bug** (user report from deployment): Client photos not displayed. `photo_url` DB field stores storage keys like `fatin-penhores/uploads/<id>/<uuid>.jpg`, but the frontend was doing `${API_BASE}/files/${photo_url}` which only works for that exact shape — absolute URLs and `/api/files/...` paths broke.
- **Frontend fix** — `/app/frontend/src/lib/api.js` new export `fileUrl(pathOrKey)`:
  - Absolute URL (`https://...`) → returned as-is
  - `/api/...` path → prefixed with `BACKEND_URL`
  - `/files/...` path → prefixed with `${API_BASE}`
  - Anything else (storage key) → returns `${API_BASE}/files/<key>`
  - Applied in `Clients.js` (list thumbnail + details modal image) and `VerifyMember.js` (public card preview).
- **Deployment issue #2 discovered by testing agent** (iter_27): the `/api/files/{path}` endpoint requires auth, so anonymous QR-scan visitors on `/verify/:token` always saw a broken image, and ReportLab's HTTP-fetch inside the server for embedding the photo in the Member Card PDF also failed.
- **Fixes** (iter_29):
  - New endpoint `GET /api/public/verify/{token}/photo` — no auth — streams object-storage bytes for the token's active card via `objstore.get_object(storage_key)`. Absolute URLs get a 307 redirect. 404 for unknown/short tokens.
  - `GET /api/public/verify/{token}` now returns `photo_url` as a full public URL pointing at the new public photo endpoint (`${PUBLIC_BASE_URL}/api/public/verify/<token>/photo`) so anonymous visitors never hit the auth-protected `/api/files/`.
  - `member_card_pdf` endpoint now loads `photo_bytes` directly via `objstore.get_object(storage_key)` when `photo_url` is a storage key / `/api/files/...` path, and passes them to `build_member_card_pdf(..., photo_bytes=...)`. Absolute URLs still fetched via HTTP as before.
  - `build_member_card_pdf` accepts new optional `photo_bytes` kwarg that short-circuits the urllib fetch.
- **Testing agent verdict** (report iter_28): **100% pass (backend 13/13, frontend 100%), 0 issues, retest_needed: false**. Verified in incognito: /verify/:token renders the photo without auth cookies. Admin thumbnails still work same-origin. Member Card PDF now embeds the actual photo (byte-delta confirmed).


## Iteration 30 (2026-02) — Payments UX + Rule A Interest Math
- **Business rule change** (Article 4): Interest is billed per **strict calendar month with a 1-day grace**. First month always billed (min 1). Payment on the monthly anniversary of the start date = same month. Payment 1 day past = new full month kicks in.
  - Examples: Jul 10 → Aug 10 = 1 month · Jul 10 → Aug 11 = 2 · Jul 20 → Aug 20 = 1 · Jul 20 → Aug 21 = 2 · Jul 1 → Jul 15 = 1.
  - Replaces the older `ceil(days_elapsed / 30)` rule.
- **Backend changes** (`/app/backend/server.py`):
  - New import `from dateutil.relativedelta import relativedelta`.
  - New helper `_months_billed(start, payment_date)` — implements Rule A.
  - `_recompute_contract_status` uses `_months_billed(...)` for `months_elapsed`; `next_interest_date = contract_start + relativedelta(months=months_elapsed) + timedelta(days=1)` (points at the day the next month kicks in).
- **Frontend changes** (`/app/frontend/src/pages/Payments.js`):
  - **New Payment dialog** summary card is now 4 metrics wide: **Interest Left** (new), Total Due, Paid, Remaining Balance. New testids: `np-interest-remaining`, `np-total-due`, `np-paid`, `np-remaining`.
  - **Disbursements table** got 2 new columns (data-appears only on the disbursement tab): **Interest / month** (`loan × rate/100`) with a `(10%)` or `(15%)` rate badge, and **Due date**. Non-disbursement tables (Payments, Overdue) unchanged.
  - Payment types (Full / Partial / Interest only) and manual Amount field unchanged — already met spec.
- **i18n**: new key `interest_per_month` (EN: "Interest / month", TET: "Juru / fulan").
- **Tests**:
  - NEW `/app/backend/tests/test_iter22_interest_rule.py` — 12 unit tests for `_months_billed` covering all edge cases (same-day, first-month, anniversary, one-day-past, end-of-month starts, leap year, payment-before-start).
  - UPDATED `/app/backend/tests/test_iter20_monthly_interest.py` — `TestArticle4MonthsElapsed` and `TestNextInterestDate` now assert Rule A instead of the old `ceil(days/30)`; canary test derives the expected value dynamically so it stays green as time moves forward.
- **Testing agent verdict** (report iter_29): **100% pass — backend 47/47 (12 unit + 5 integration + 30 regression), frontend 100%, retest_needed: false**. Final local run: 27/27 pytest tests green.


## Iteration 31 (2026-02) — Interest Calculation Explainer on Receipt PDF
- `build_receipt_pdf` now renders a soft-indigo "Oinsá ami sura interese-nia · How your interest was calculated" block right after the amber Next Payment note.
- Content (bilingual EN/TET):
  - Contract Start · Payment Date
  - Billing Months (Article 4) — e.g. "2 months · 2 fulan"
  - Rate × Loan (per month) — e.g. $150.00
  - Interest Charged — inline expression like `2 × $150.00 = $300.00`
  - Explainer footer explaining Rule A (anniversary = same month, +1 day = new month).
- Wrapped in try/except so a bad field never breaks receipt generation.
- Skipped on disbursement receipts (already gated by `not is_disbursement`).
- Verified: PDF now embeds the block; AI-inspection of a real receipt confirmed all 5 rows render correctly on the indigo panel with the bilingual explainer paragraph below.


## Iteration 32 (2026-02) — WhatsApp Overdue Reminders now include interest math
- **Extended templates** `_MSG_EN` and `_MSG_TET` in `/app/backend/reminders.py` to include the same Rule A interest math the receipt PDF shows:
  - Line 1: brand
  - Line 2: `Hello {name}` / `Ola {name}`
  - Line 3: `Contract {short_number} is {days} days overdue.`
  - Line 4: `Owed today: ${loan} + {months}×${per_month} interest = ${total_due}.`
  - Line 5: `On {next_month_date} interest rises to ${next_interest_total}.`
  - Line 6: `Please pay within {days_left} more days to avoid auction.`
  - Line 7: WhatsApp footer
  - Both languages stay ≈ 250 chars, well under WhatsApp's 1024 free-form limit.
- **Refactor** — extracted `_months_billed` into `deps.py` as `months_billed(start, payment_date)` so both `server.py` and `reminders.py` share the same Rule A math (no circular import). `server.py` still exposes the old alias `_months_billed` for internal callers/tests.
- **Reminder scheduler** loads `contract_date` in its DB projection and calls the shared helper. `days_left` calc unchanged (max(0, 10 - days)).
- **Tests** — NEW `/app/backend/tests/test_iter23_reminder_body.py` (5 tests): EN body math, TET body math + language, length ≤ 500 chars, `_short_contract` helper, business-owner concrete scenario (Jul 10 → Aug 5 = 1×$50=$550, next 2026-08-11 = $100).
- **Testing agent verdict** (report iter_30): **100% pass — backend 62/62 (5 iter23 unit + 12 iter22 unit + 15 iter20 unit + 3 iter30 integration + 27 iter17 regression), 0 issues, retest_needed: false**. Scheduler boots cleanly. Admin `POST /api/reminders/run?force=true` returns a valid summary. Rule A math validated end-to-end via GET /api/contracts/{id}.


## Iteration 33 (2026-02) — A11y + TET Translation Polish + Ad-hoc WhatsApp Preview & Send
- **A11y fix** — Added `<DialogDescription className="sr-only">` (or visible where appropriate) to every admin Dialog to resolve Radix's `aria-describedby` console warning. Files touched: `Payments.js` (New Payment + Overdue Payment), `Clients.js` (Create/Edit + Details), `Auctions.js` (Mark Sold), `Contracts.js` (New Contract + Reactivate + new WA Preview modal).
- **TET translation gap on Payments**:
  - Type badges in Payments/Overdue/Disbursement tables now render via `t(r.type)` instead of the raw enum string — so `full`, `partial`, `interest_only`, `disbursement`, `overdue_full`, `overdue_interest_pen`, `overdue_penalty_only` all switch to the Tetum labels (Kompletu / Parsiál / Juru Deit / Entrega Empréstimu / etc.).
  - New i18n keys added in both EN and TET blocks in `i18n.js` for badge labels and the `disbursements` tab title. Tab now displays `Entrega Empréstimu (15)` under TET.
- **Ad-hoc "Preview & Send" WhatsApp reminder** — cashiers/staff can now review + edit the Rule A math message body before sending, rather than firing the templated message blindly. Lives on the Contracts page per-contract action button (both pre-auction table `pa-whatsapp-{id}` and main table `contract-whatsapp-{id}`).
  - **Backend** — `/app/backend/reminders.py` gained `build_reminder_body(contract, client_name, language, today=None)` which returns `{body, days, months, per_month, total_due, next_month_date, language}`. Both the daily scheduler and the new ad-hoc endpoints reuse it, so the message math never drifts.
  - Two new endpoints (both authenticated):
    - `POST /api/whatsapp/preview` — returns the rendered body + client name/phone + Rule A metadata for the given `contract_id` + `language` (`en`/`tet`).
    - `POST /api/whatsapp/adhoc-send` — sends a free-form (optionally edited) body to `to_phone` (defaulting to client's phone) via `wapp.send_text`. Falls back to `mocked` when Meta creds aren't configured. Writes an audit log + a `whatsapp_log` row with `template="adhoc_text"`.
  - **Frontend** (`Contracts.js`) — `sendWhatsApp` no longer fires-and-forgets; it opens a new `wa-preview-dialog` modal that fetches `/whatsapp/preview`, shows a meta pill (Contract#, Client, Days overdue, Total due), lets the user tweak the `To` phone, switch language (EN/TET dropdown), edit the message body in a `Textarea`, hit `Regenerate` to reset from the template, and finally `Send` via `/whatsapp/adhoc-send`. Character counter + disabled Send while empty. New testids: `wa-preview-dialog`, `wa-to-phone`, `wa-lang`, `wa-body`, `wa-regenerate`, `wa-send`.
- **Tests** — NEW `/app/backend/tests/test_iter24_whatsapp_adhoc.py` (6 tests): EN preview shape + Rule A math verified against a 45-day-old contract (months=2, total_due=$600), TET preview language check, unknown-contract 404, auth required, mocked adhoc-send round-trip, empty-body rejection. **All 6 PASS.** Combined regression: iter22 + iter23 + iter20 unit tests → 32/32 PASS.


## Iteration 35 (2026-02) — Rule M1 (Method 1 payment allocation)
The business owner clarified that partial payments should follow Method 1
(interest-first, then principal) — standard lending accounting practice. This
correctly rewards clients for early partial payments by lowering next-month
interest on the remaining balance.

### Business rule (verified against owner examples)
- **Payment allocation (Method 1):** Interest Paid = MIN(payment, unpaid_interest);
  Principal Paid = MAX(payment − unpaid_interest, 0).
- **Month 1 interest** = 10% × original loan (Rule A anchor — one full month
  always guaranteed).
- **Month N > 1 interest** = 10% × Remaining Principal at Month N anchor
  (declining balance — never compounds unpaid interest per owner's
  "no aggressive compound" instruction).
- **No compounding on delinquency:** If client pays nothing, next month's
  interest is still 10% × Principal (not 10% × Outstanding).

### Business owner examples (all verified end-to-end)
- **Example 1 — $3,000 loan, $1,000 partial:**
  - Interest paid: $300, Principal paid: $700, Principal remaining: $2,300
  - Next month interest: **$230** (10% × $2,300) ✅
  - Total if unpaid: $2,300 + $230 = $2,530
- **Example 2 — $3,000 loan, $300 interest-only:**
  - Interest paid: $300, Principal paid: $0, Principal remaining: $3,000
  - Next month interest: **$300** ✅
- **No-payment case:** Next month interest: **$300** (NOT $330 — no compound) ✅

### Implementation
- New field `interest_rule` on the `contracts` collection:
  - `"M1"` (default for new contracts) → interest-first allocation
  - `"M2"` (legacy default when field absent) → all-to-principal allocation
- `services.py._recompute_contract_status` — rewritten with event-driven
  chronological walk. Merges month-anchor events with payment events, walks in
  date order, and applies the M1/M2 allocation rule per contract.
- Contract creation (`POST /api/contracts`) sets `interest_rule="M1"` on all
  new contracts. Existing contracts remain on legacy M2 semantics — no
  retroactive impact.
- `pdf_utils.py` receipt "How your interest was calculated" block now shows
  the per-month itemized breakdown (e.g. `$300 + $230 + $230 + ...`) when the
  hybrid declining-balance rates apply.
- `reminders.py.build_reminder_body` prefers the recomputed contract's
  values so WhatsApp/email reminders show the correct M1 totals.
- Frontend `Payments.js` disbursement tooltip updated: "Current-month interest
  (Rule M1: interest-first allocation, principal-remaining base)."

### Tests (all passing)
- NEW `tests/test_iter27_rule_m1.py` (5 tests):
  - Example 1: partial $1000 → interest paid=$300, principal paid=$700, next month=$230 ✅
  - Example 2: interest-only $300 → next month=$300 ✅
  - No compounding on delinquency: next month=$300 (not $330) ✅
  - Legacy M2 contracts: partial=principal-only, next month=$200 (backwards-compat) ✅
  - Two partials stack: month 2=$280 (10% × $2,800), month 3=$258 (10% × $2,580) ✅
- Adjusted `tests/test_iter4.py::test_partial_reduces_principal` to reflect
  M1 semantics (was asserting old M2 all-to-principal).
- Adjusted `tests/test_iter26_rule_b_hybrid.py` to explicitly pass
  `interest_rule="M2"` for backwards-compat verification.
- **Total regression: 361/367 tests pass** (6 pre-existing failures unrelated
  to this iteration — public warehouse gates + settings defaults).


## Iteration 34 (2026-02) — Phase 2 Refactor + Audit Log UI + Resend Email + Auth Extras + PWA
This is a big batch of P0/P2 backlog items shipped together. Broken down:

### P0 — Backend refactor Phase 2 (server.py split into routers)
- `services.py` NEW (~276 lines) — cross-domain helpers: `_recompute_contract_status` (Rule A interest math), `_fetch_item`, `get_settings_doc`, `_decrypted_settings`, `_send_reminder_for_contract`, `_wa_template_name`, `_wa_lang_code`, `_today_iso`, `_ym_from_iso`, `_apply_date_filter`, `DEFAULT_SETTINGS`, `ITEM_KINDS`. Prevents circular imports between routers.
- `routes/reports.py` NEW (~470 lines) — v1 + v2 endpoints, KPI aggregations, CSV/XLSX/PDF exports, all `_report_*` builders.
- `routes/finance.py` NEW (~360 lines) — funding sources CRUD + repayments + operating expenses + finance summary + 3 PDF exports.
- `routes/public.py` NEW (~149 lines) — public auction items, warehouse password gate, contact form.
- `routes/whatsapp.py` NEW (~222 lines) — WhatsApp send / preview / adhoc-send / test / logs / reminders/run.
- `routes/admin.py` NEW (~212 lines) — backup list/generate/download + health + enhanced audit log endpoints.
- `routes/auth_extra.py` NEW (~173 lines) — forgot-password / reset-password / admin manual reset.
- `server.py` shrunk from **2905 lines → 1555 lines** (~46% reduction). All API paths and behaviour unchanged.
- `models.py` deferred (keeping Pydantic models close to their handlers turned out cleaner).

### P2 — Audit Log Viewer UI (admin sees who changed what)
- Backend enhancements to `GET /api/audit-log`: added filters `action`, `actor_email` (case-insensitive substring), `date_from`, `date_to`. Added indexes on `resource`, `action`, `actor_email`.
- NEW `GET /api/audit-log/export/csv` — respects filters, returns text/csv attachment.
- NEW `GET /api/audit-log/export/pdf` — branded landscape PDF via `build_audit_log_pdf` in `pdf_utils.py` with filter summary + table.
- Full frontend rewrite `/app/frontend/src/pages/AuditLog.js` — filter bar (Resource / Action / Actor email / From / To / Limit), Reset + Apply buttons, coloured CSV / PDF export buttons, live row count in header.

### P2 — Email reminders via Resend (fallback when client has no phone)
- `resend==2.32.2` installed.
- NEW `email_svc.py` — Resend SDK wrapper with **graceful mocked fallback** (matches WhatsApp UX). Uses `asyncio.to_thread` for non-blocking sends. Two ready-made HTML templates: `render_overdue_reminder` (bilingual Rule A math body) + `render_password_reset`.
- New env vars: `RESEND_API_KEY=""` and `SENDER_EMAIL="onboarding@resend.dev"` (sandbox — verified domain later).
- Reminder scheduler (`reminders.py`) now: (a) prefers WhatsApp when phone present + WA configured, (b) **falls back to email only when client has no phone number** (per admin choice), (c) records `channel` and `recipient` in the send summary so admin can distinguish.
- MOCKED — will remain mocked until admin drops the Resend API key into `.env`.

### P2 — "Remember me" + Forgot password flow + PWA
- `auth.py` — `create_refresh_token(user_id, remember=False)` and `set_auth_cookies(..., remember=False)` now support the "Remember me" 30-day path (was hardcoded 7d). `POST /api/auth/refresh` preserves the `remember` claim from the current refresh token.
- `LoginIn` gained `remember: bool = False` — the /login endpoint honours it.
- NEW `POST /api/auth/forgot-password` — always returns generic 200 (email enumeration safe). When email exists, mints a 15-min single-use `secrets.token_urlsafe(48)`, wipes any prior unused tokens for that user, stores in `password_reset_tokens`, fires the reset link email.
- NEW `GET /api/auth/reset-token-info?token=…` — public preflight for the /reset-password page; returns masked email + expiry.
- NEW `POST /api/auth/reset-password` — consumes the token exactly once, bcrypt-hashes new password, marks `used_at`.
- NEW `POST /api/users/{id}/reset-password` — admin-only manual reset. Also invalidates any outstanding self-service tokens for that user.
- Frontend:
  - Login page: **Remember me** checkbox + **Forgot password?** link (both fully bilingual EN/TET).
  - NEW `/forgot-password` public page — email form → success card.
  - NEW `/reset-password?token=…` public page — token preflight → new password + confirm → success → auto-redirect to /login.
  - Users page: **KeyRound** (amber) icon button per row (admin-only) → `window.prompt` → `/users/{id}/reset-password`.
- PWA installability:
  - NEW `public/manifest.json` — Fatin Penhores metadata, navy theme, standalone display, `/dashboard` start URL, logo as maskable icon.
  - NEW `public/service-worker.js` — minimal install/activate handler + shell cache. **Never** caches `/api/*` — financial data always live.
  - `index.html`: `<link rel="manifest">`, apple-touch-icon, apple-mobile-web-app-* meta tags, navy `theme-color`.
  - `index.js`: SW registered only in `NODE_ENV=production` (no stale-cache annoyance in dev).
- New i18n keys (EN + TET): `remember_me`, `forgot_password`, `reset_password`, `reset_password_desc`, `reset_password_sent`, `reset_new_password`, `reset_confirm`, `reset_password_success`, `reset_link_expired`, `passwords_dont_match`, `back_to_login`.

### Tests
- NEW `tests/test_iter25_auth_extras_and_audit.py` — 8 tests covering: Remember-me 30d cookie, default 7d cookie, forgot→reset→login cycle, token single-use (410), admin manual reset happy + RBAC path, audit CSV export MIME/format, audit PDF export MIME + %PDF magic + minimum size. **All 8 PASS.**
- Regression: 350 pytest tests PASS after the refactor. 6 pre-existing failures (public auction/warehouse gates + iter2 defaults + iter27 photo sizing) are unrelated and were already failing before this session.

### Backlog cleared
- ~~P0: Refactor server.py Phase 2~~ ✅
- ~~P2: Audit log viewer UI~~ ✅
- ~~P2: Email reminders via Resend~~ ✅ (mocked until API key provided)
- ~~P2: PWA install + Remember me + Forgot password~~ ✅


## Prioritized Backlog
### P2 — UI Polish (still open)
- Color-coded tabs on Reports page (match Items/Finance).
- Recharts `ResponsiveContainer` width(-1) warning on Dashboard/Finance — wrap charts with `min-h-[300px]`.

### P3 — Enhancements
- Home page hero redesign (full Tetum match: hero copy, category mosaic, 4-step process, testimonials).
- Verify a real domain on Resend and switch `SENDER_EMAIL` away from the sandbox so we can email any client (not just the account owner).
- Tighten backend Pezadu category validation with `Literal[...]` enum.
- Hard-fail Settings PUT when `WHATSAPP_ENCRYPTION_KEY` missing (avoid silent plaintext storage).
- Split `server.py` further (auth + users + clients + items + contracts + payments + auctions) — the remaining 1555 lines are still substantial. Second refactor pass when a low-risk window opens.
- Move contract status recompute out of report GET into a background job for perf.

## Credentials
- Admin: `admin@fatinpenhores.tl` / `admin123` (see `/app/memory/test_credentials.md`).
- WhatsApp creds: set via Settings → WhatsApp Configuration. Empty = MOCKED.
- Resend: `RESEND_API_KEY=""` in `/app/backend/.env` — set to a real `re_...` key from https://resend.com/api-keys to enable actual email delivery. Empty = MOCKED.
