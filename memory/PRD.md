# PRD — Fatin Penhores Pawn System

**Last updated:** 2026-02 (Iteration 2)

## Original Problem Statement
Pawn shop management system for Fatin Penhores (Dili, Timor-Leste). Modules: Dashboard, Client Management, Pawn Item Management (separate tables for Car, Motorcycle, Electronic), Pawn Contract Module (CTR-YYYY-#### numbering, 10/15% interest, statuses), Payment Module (full/partial/interest-only), Auction Module, Reports, PDF/Print, User Account/Admin Module, Public Website.

Flow: Client → Pawn Item → Contract → Payment → Redeem / Auction → Report.

## User Personas
- **Admin** — full access including users, settings, audit log, and deletions.
- **Staff** — clients, items, contracts, payments, auctions (no user mgmt, no settings).
- **Cashier** — payments only; can read contracts/clients/items.
- **Public visitor** — public site, contact form, auction listings.

## Architecture
- **Backend**: FastAPI (Python), MongoDB (motor async). JWT in httpOnly cookies. PDFs via ReportLab. Object storage via Emergent integrations. WhatsApp Cloud API (Meta).
- **Frontend**: React 19 + react-router v7 + Shadcn/UI + Tailwind + Recharts. Bilingual EN/TET.
- **Collections**: users, clients, cars, motorcycles, electronics, contracts, payments, auctions, contact_messages, settings, files, audit_log, whatsapp_log.

## Implemented (Iteration 1 — 2026-02)
- Auth (login/logout/me/refresh) with bcrypt + JWT cookies; admin seeded from env.
- Clients CRUD with Timor-Leste address taxonomy.
- Three separate item collections (cars / motorcycles / electronics).
- Contracts with CTR-YYYY-#### number, 10/15% interest, status recomputation, remaining balance.
- Payments (full / partial / interest-only) with RCP-YYYY-#### receipts; auto-redeem on full payment.
- Auction flow: move overdue → public listing → mark sold.
- Reports (loans, payments, profit, overdue, clients, contracts) + CSV export.
- Contract PDF + Payment Receipt PDF.
- User management (admin only).
- Public site: Home, Auction items, Warehouse, About, Contact.

## Implemented (Iteration 2 — 2026-02)
- **Settings page** (admin) — interest rate defaults per item type (Car 10%, Motorcycle 15%, Electronic 15%), bilingual T&C templates (EN + TET), WhatsApp credentials & template names, reminder window.
- **Default interest by item type** auto-applied on new contracts (override still allowed).
- **Richer contract PDF** — full client section, kind-specific item details, loan breakdown, embedded T&C (EN + TET), signature lines.
- **Object storage uploads** — photo + document for items (Car / Motorcycle / Electronic) via Emergent storage. Files served via `/api/files/{path}`.
- **Dashboard charts (Recharts)** — monthly trends (loans · payments · interest) and overdue-by-item-type bar chart.
- **Cashier role** — RBAC enforced on POST /clients, /items, /contracts; cashier limited to payments.
- **Audit log** — writes on contract create, payment create, settings update, client create, item create, WhatsApp send. Admin-only read at `/audit-log`.
- **WhatsApp Cloud API (Meta direct)** — `/api/whatsapp/send` per contract + `/api/whatsapp/reminders/run` scheduler endpoint. Safe MOCK mode when token absent (logs to DB).
- **Language toggle EN ↔ TET** (relabeled from PT).

## Test Coverage
- Backend: 33/33 (iteration 1) + 22/22 (iteration 2) passing after all fixes.
- Frontend: end-to-end verified — LangToggle on /login, Settings save+persist, Audit log table, FileUpload component, WhatsApp send button (mocked).

## Prioritized Backlog
### P1 — Suggested next phase
- Email notifications via Resend / SendGrid (alongside WhatsApp).
- Real Meta WhatsApp credentials in Settings (currently mocked).
- Approved WhatsApp message templates (`due_date_reminder` EN + TET).
- Daily reminders scheduler (cron job or Emergent scheduled task).
- Dashboard date-range filter.

### P2
- Refactor `server.py` (now ~1200 lines) into routers per domain.
- Audit log on item update / delete (currently only create).
- Dedicated cashier-only UI shell.

## Credentials
- Admin: `admin@fatinpenhores.tl` / `admin123` (see `/app/memory/test_credentials.md`).
- WhatsApp token + Phone Number ID: set via Settings → WhatsApp Configuration.
