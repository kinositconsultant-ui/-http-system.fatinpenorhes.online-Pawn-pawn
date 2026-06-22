# PRD — Fatin Penhores Pawn System

**Last updated:** 2026-02

## Original Problem Statement
Build a pawn shop management system for Fatin Penhores (Timor-Leste) covering: Dashboard, Client Management, Pawn Item Management (separate tables for Car, Motorcycle, Electronic), Pawn Contract Module (CTR-YYYY-#### numbering, 10/15% interest, statuses), Payment Module (full/partial/interest-only), Auction Module, Reports, PDF/Print, User Account/Admin Module, and a Public Website (Home, Auction items, Warehouse, About, Contact).

System flow: Client → Pawn Item → Contract → Payment → Redeem / Auction → Report.

## User Personas
- **Admin** — full access to all modules including user management and deletion.
- **Staff** — day-to-day clerk operations (clients, items, contracts, payments, auctions). Cannot delete users or clients.
- **Public visitor** — browses public site, contact form, public auction listings.

## Architecture
- **Backend**: FastAPI (Python), MongoDB (motor async). JWT in httpOnly cookies. PDFs via ReportLab.
- **Frontend**: React 19 + react-router-dom v7 + shadcn UI + Tailwind. Bilingual EN/PT via lightweight i18n context.
- **Auth**: JWT (HS256), access 8h / refresh 7d in httpOnly cookies; admin seeded from .env.
- **Collections**: users, clients, cars, motorcycles, electronics, contracts, payments, auctions, contact_messages.

## What's Been Implemented (2026-02)
- Auth (login/logout/me/refresh) with bcrypt + JWT cookies. Admin seeded on startup.
- Client CRUD with full Timor-Leste address taxonomy (municipality/posto/suco/aldeia).
- Three separate item collections (cars / motorcycles / electronics) with kind-specific fields (plate/chassis/fuel% for vehicles, category/serial for electronics).
- Contracts with auto CTR-YYYY-#### number, 10/15% interest, status recomputation (active/overdue/redeemed/auction) and remaining balance.
- Payments (full / partial / interest-only) with RCP-YYYY-#### receipt numbers. Full payment auto-redeems contract & item.
- Auction flow: move overdue → public listing → mark sold (releases item).
- Reports (loans, payments, profit, overdue, clients, contracts) + CSV export.
- PDF generation: contract PDF and payment receipt PDF.
- User management (admin only): create/delete staff and admins; cannot delete self.
- Public site: Home (hero + values + CTAs), Auction items grid, Warehouse with filters, About, Contact form.
- Bilingual EN/PT toggle across all pages.

## Test Coverage
- Backend pytest suite at `/app/backend/tests/backend_test.py` — 33/33 passing.
- Frontend end-to-end verified (all data-testid attributes, public + admin flows, language toggle, logout).

## Prioritized Backlog
### P0 — Done
- All modules above are complete and tested.

### P1 — Suggested next phase
- Photo / document upload via object storage (currently text URL fields).
- Email/WhatsApp reminders for upcoming due dates.
- Dashboard charts (Recharts) for monthly profit and overdue trend.
- Print-friendly views for in-shop kiosk usage.

### P2 — Nice to have
- Multi-currency support (currently USD only).
- Role: cashier (payments-only).
- Audit log for status changes.
- Refactor: split `server.py` into routers per domain.

## Credentials
- Admin: `admin@fatinpenhores.tl` / `admin123` (see `/app/memory/test_credentials.md`).
