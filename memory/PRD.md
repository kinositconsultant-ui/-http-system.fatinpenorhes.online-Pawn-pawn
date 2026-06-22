# PRD — Fatin Penhores Pawn System

**Last updated:** 2026-02 (Iteration 3)

## Original Problem Statement
Pawn shop management system for Fatin Penhores (Dili, Timor-Leste). Modules: Dashboard, Client Management, Pawn Item Management (separate tables for Car, Motorcycle, Electronic), Pawn Contract Module (CTR-YYYY-#### numbering, 10/15% interest, statuses), Payment Module (full/partial/interest-only), Auction Module, Reports, PDF/Print, User Account/Admin Module, Public Website.

Flow: Client → Pawn Item → Contract → Payment → Redeem / Reactivate / Auction → Report.

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

## Test Coverage
- Backend: **77/77 PASS** across iter1 (33) + iter2 (22) + iter3 (22).
- Frontend: all data-testid selectors verified — photo upload, Drivers License option, view dialog with contracts + payment history tables, market_value + manufacture_year inputs, Reactivate dialog, Penalty column.

## Prioritized Backlog
### P1 — Next phase
- Email notifications via Resend / SendGrid alongside WhatsApp.
- Daily scheduled job to auto-trigger `/api/whatsapp/reminders/run` (cron / Emergent scheduled task).
- Real Meta WhatsApp token + approved templates (`due_date_reminder` EN + TET) configured by user in Settings.
- Dashboard date-range filter.
- Stamp `last_penalty_applied` on contracts on reactivate (audit history).

### P2
- Split `server.py` (~1320 lines) into routers (clients/items/contracts/payments/auctions/files/whatsapp/audit/dashboard/settings).
- Audit log on item update / delete (currently only on create).
- Shadcn Calendar in date pickers (currently native).
- Dedicated cashier UI shell.

## Credentials
- Admin: `admin@fatinpenhores.tl` / `admin123` (see `/app/memory/test_credentials.md`).
- WhatsApp creds: set via Settings → WhatsApp Configuration. Empty = MOCKED.
