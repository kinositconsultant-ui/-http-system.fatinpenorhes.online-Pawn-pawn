# Fatin Penhores — System Topology & Payment Calculation
_Version: Feb 2026 · Rule M1_

This document explains how the Fatin Penhores pawn management system is
structured (Section 1) and exactly how interest and payment allocation are
computed (Section 2). Share it with staff, auditors, or your accountant.

---

## 1. System Topology

### 1.1 High-level architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            USERS                                          │
│  Admin / Manager / Cashier · Clients (public verify) · Warehouse guests   │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │  HTTPS (JWT httpOnly cookie)
                        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    FRONTEND — React 18 + TailwindCSS                      │
│  /app/frontend                                                            │
│  ─────────────                                                            │
│  • Pages: Dashboard · Clients · Items · Contracts · Payments · Auctions   │
│           Finance · Reports · Settings · AuditLog · Users                 │
│  • Public: Home · Services · FAQ · VerifyMember · Login / Forgot / Reset  │
│  • Layouts: AdminLayout (mobile drawer) · PublicLayout                    │
│  • i18n: EN / TET context (LangContext)                                   │
│  • PWA: manifest.json + service-worker.js (Add-to-Home-Screen)            │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │  /api/* via REACT_APP_BACKEND_URL
                        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                 BACKEND — FastAPI (Python 3.11) · port 8001               │
│  /app/backend                                                             │
│  ─────────────                                                            │
│                                                                           │
│  server.py (1,555 lines) — app bootstrap + auth + clients/items/contracts│
│                             /payments/auctions/settings/dashboard         │
│                                                                           │
│  routes/                                                                  │
│   ├─ reports.py     — v1 + v2 KPIs, CSV/XLSX/PDF exports                  │
│   ├─ finance.py     — capital sources, expenses, summary, exports         │
│   ├─ public.py      — /public/verify · /public/auction-items · warehouse  │
│   ├─ whatsapp.py    — /whatsapp/send · /preview · /adhoc-send · /logs     │
│   ├─ admin.py       — /audit-log (+CSV/PDF), /backups                     │
│   └─ auth_extra.py  — /auth/forgot-password · /reset-password             │
│                                                                           │
│  services.py — SHARED HELPERS (imported by all route modules)             │
│   ├─ _recompute_contract_status()  ◄── INTEREST MATH LIVES HERE           │
│   ├─ _fetch_item()                                                        │
│   ├─ get_settings_doc() / _decrypted_settings()                           │
│   └─ _send_reminder_for_contract() + WhatsApp helpers                     │
│                                                                           │
│  Supporting modules                                                       │
│   ├─ auth.py         — JWT create/verify, cookies, Remember me            │
│   ├─ deps.py         — RBAC guards, `months_billed()`, `write_audit()`    │
│   ├─ pdf_utils.py    — Contract/Receipt/Invoice/Disbursement/Card PDFs    │
│   ├─ email_svc.py    — Resend wrapper w/ mocked fallback                  │
│   ├─ whatsapp.py     — Meta Cloud API wrapper w/ mocked fallback          │
│   ├─ reminders.py    — Daily reminder builder (Rule M1 body)              │
│   ├─ scheduler.py    — APScheduler: daily backup + daily reminders        │
│   ├─ storage.py      — Object storage helpers                             │
│   └─ encryption.py   — Fernet symmetric encryption for stored secrets     │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
        ┌───────────────┼──────────────┬──────────────┬─────────────┐
        ▼               ▼              ▼              ▼             ▼
   ┌─────────┐   ┌────────────┐  ┌─────────┐  ┌────────────┐  ┌──────────┐
   │ MongoDB │   │ Emergent   │  │ WhatsApp│  │ Resend     │  │ Local FS │
   │ (motor) │   │ Object     │  │ Cloud   │  │ (email)    │  │ /backups │
   │         │   │ Storage    │  │ API     │  │ MOCKED     │  │ daily zip│
   │ clients │   │ (photos,   │  │ MOCKED  │  │ until key  │  │ 30-day   │
   │ items   │   │ PDFs)      │  │ until   │  │ set        │  │ retention│
   │ contracts│  │            │  │ token   │  │            │  │          │
   │ payments │  │            │  │ set     │  │            │  │          │
   │ auctions │  └────────────┘  └─────────┘  └────────────┘  └──────────┘
   │ users    │
   │ settings │
   │ audit_log│
   │ pw_reset_│
   │  tokens  │
   └─────────┘
```

### 1.2 Key operational flows

**A. Pawn Contract lifecycle**
```
Client walks in
   │
   ▼
[1] Create Client   ────────────►  POST /api/clients
   │
   ▼
[2] Create Item (car/motorcycle/electronic/pezadu)  ──►  POST /api/items/{kind}
   │  (uploaded photo → object storage → photo_url)
   ▼
[3] Create Contract ────────────►  POST /api/contracts
   │  • assigns contract_number (CTR-YYYY-NNNN)
   │  • sets interest_rule = "M1" (Feb 2026+)
   │  • marks item as "pawned"
   ▼
[4] Disbursement payment ─────►  POST /api/payments (type="disbursement")
   │  → records $ handed over to client, PDF disbursement receipt
   ▼
[5] Client repays over time
       ├─ interest_only  ($X → all to interest, excess to principal)
       ├─ partial        ($X → interest first (M1), then principal)
       ├─ full           (redeems the contract)
       └─ overdue_full / overdue_interest_pen / overdue_penalty_only
   ▼
[6] Status auto-computed on every read (services.py)
       active → overdue (past due_date)
              → auction_ready (>10 days overdue)
              → auction (staff moves it)
              → sold (auction closed with buyer)
              → redeemed (principal + interest + penalty all $0)
```

**B. Daily automated jobs (APScheduler)**
```
02:00 UTC  ──► scheduler.py.run_daily_backup()
              └── MongoDB dump → zip → /app/backups/YYYY-MM-DD.zip
              └── 30-day retention

09:00 UTC  ──► reminders.py.run_daily_reminders()
              └── Find overdue contracts (day 7 & day 9)
              └── Prefer WhatsApp if phone + WA configured
              └── Fallback to email if no phone (Resend, when configured)
              └── Log every attempt to db.whatsapp_log
              └── Audit log entry
```

**C. Public endpoints (no auth)**
```
GET /api/public/verify/{token}         → JSON: member name + expiry
GET /api/public/verify/{token}/photo   → member photo (used in <img src>)
GET /api/public/auction-items          → open catalogue (with warehouse gate)
GET /api/public/warehouse              → password-gated open items
POST /api/public/contact               → contact form
```

**D. Authentication flow**
```
LOGIN:
POST /api/auth/login  {email, password, remember}
  → verify_password (bcrypt)
  → create_access_token (8h)
  → create_refresh_token (7d default, 30d if remember=true)
  → set_auth_cookies (httpOnly, secure, SameSite=none)

FORGOT PASSWORD:
POST /api/auth/forgot-password  → email link (15-min single-use token)
GET  /api/auth/reset-token-info?token=XX  → preflight (masked email)
POST /api/auth/reset-password  → set new password, invalidate token

ADMIN OVERRIDE:
POST /api/users/{id}/reset-password  → in-person reset by admin
```

---

## 2. Payment Calculation Logic — Rule M1

### 2.1 One-sentence summary
> Every partial payment first clears **unpaid interest**, then reduces
> **principal**. Next month's interest is 10% of the **remaining principal
> only** (not the outstanding balance — no compounding on unpaid interest).

### 2.2 Key variables

| Symbol | Meaning |
|---|---|
| `L` | Original loan amount |
| `R` | Monthly interest rate (as fraction, e.g. 0.10 for 10%) |
| `P` | Principal remaining (starts at `L`, drops as principal is paid) |
| `U` | Unpaid interest (accumulates monthly, drops when interest is paid) |
| `C` | Payment amount |
| `N` | Month number (1, 2, 3, ...) since contract start |

### 2.3 Interest accrual formula

At the start of each billing month `N` (anniversary of the contract date, one
grace day per Article 4 — Rule A timing):

```
if N == 1:
    Month_Interest[1] = L × R            (anchor month — always original loan)
else:
    Month_Interest[N] = P × R            (declining balance on principal only)

U ← U + Month_Interest[N]                (adds this month's interest to unpaid)
```

### 2.4 Payment allocation formula (Method 1 — Interest First)

When a payment `C` arrives on any date:

```
Interest_Paid  = MIN(C, U)               (clear as much unpaid interest as possible)
Principal_Paid = MAX(C − U, 0)           (remainder reduces principal)
U  ← MAX(U − C, 0)                       (new unpaid interest)
P  ← P − MIN(C − U_before, P)            (new principal, capped at P)
```

### 2.5 Predicted next-month interest (shown on receipt)

```
Next_Month_Interest = P × R              (uses CURRENT remaining principal)
```

**Important:** We do **NOT** use `(P + U) × R` — that would compound unpaid
interest into the next-month base. The business owner explicitly opted out of
that behaviour ("no aggressive compounding").

### 2.6 Worked examples

**Example 1 — Partial payment > accrued interest**

```
Loan L = $3,000, Rate R = 10%, Contract start Jan 10

Month 1 anchor (Jan 10):
  Month_Interest[1] = 3000 × 0.10 = $300
  U = $300, P = $3,000

Jan 20 — client pays C = $1,000 (type=partial, Method 1):
  Interest_Paid  = MIN(1000, 300) = $300
  Principal_Paid = MAX(1000 - 300, 0) = $700
  U = $0
  P = $3,000 - $700 = $2,300

  Outstanding = P + U = $2,300

Month 2 anchor (Feb 10):
  Month_Interest[2] = P × R = 2300 × 0.10 = $230   ◄── declining balance
  U = $230

Next month forecast shown on receipt:
  Next_Month_Interest = 2300 × 0.10 = $230
  New total if unpaid = P + U + Next_Month_Interest
                      = 2300 + 0 + 230 = $2,530
```

**Example 2 — Interest-only payment**

```
Loan L = $3,000, Rate R = 10%
Month 1: U = $300, P = $3,000

Client pays C = $300 (type=interest_only):
  Interest_Paid  = MIN(300, 300) = $300
  Principal_Paid = 0
  U = $0
  P = $3,000

Month 2 anchor: Month_Interest[2] = 3000 × 0.10 = $300
Next forecast: $300  ◄── same, because principal unchanged
```

**Example 3 — No payment at all (compound guard)**

```
Loan L = $3,000, Rate R = 10%
Month 1: U = $300, P = $3,000

Month 2 anchor:
  Month_Interest[2] = P × R = 3000 × 0.10 = $300
  U = $300 + $300 = $600  (accumulates but doesn't compound the base)

Next forecast: still $300 (10% × $3,000 principal, NOT 10% × $3,600 outstanding)
```

**Example 4 — Small partial (< interest owed)**

```
Loan L = $3,000, U = $300, P = $3,000

Client pays C = $200 (type=partial):
  Interest_Paid  = MIN(200, 300) = $200
  Principal_Paid = MAX(200 - 300, 0) = 0
  U = $100    (still $100 unpaid interest)
  P = $3,000  (principal unchanged)

Month 2 anchor:
  Month_Interest[2] = 3000 × 0.10 = $300
  U = $100 + $300 = $400

Next forecast: $300  ◄── based on principal only (no compounding on the $100)
```

### 2.7 Payment types & rules

| Type | Allocation | Notes |
|---|---|---|
| `disbursement` | Not applied — records loan handover to client | PDF: disbursement receipt |
| `interest_only` | Interest first, then principal | Standard monthly repayment |
| `partial` | **M1 → interest first, then principal** | Was M2 (all-to-principal) pre-Feb 2026 |
| `full` | Interest first, then principal → redeems contract | Contract closes |
| `overdue_full` | Penalty first → interest → principal | Triggers when past due_date |
| `overdue_interest_pen` | Penalty first → interest (no principal) | Client wants to keep the debt alive |
| `overdue_penalty_only` | Penalty only | Buys time before principal payoff |

**Penalty:** 10% flat on original loan, applied once when the contract goes
overdue (`due_date` past). Cleared as it's paid down.

### 2.8 Contract status transitions

```
active
   │
   │ (due_date passes)
   ▼
overdue  ──►  penalty accrues (10% × L, one-time)
   │
   │ (10+ days past due_date)
   ▼
auction_ready  ──►  staff moves item to auction
   │
   ▼
auction  ──►  buyer bids → invoice created
   │
   ▼
sold  (or) redeemed (if client pays before auction closes)
```

### 2.9 Rule versioning per contract

- Contracts created **on/after Feb 2026** have `interest_rule = "M1"` (this
  document's rules).
- Contracts created **before** the rule change have `interest_rule = "M2"`
  implicit (partial = all to principal, no interest-first split). Existing
  contracts keep their historical calculation to avoid disputes — the code
  branches on this field per contract.

### 2.10 Where each formula lives in code

| Concern | File | Function |
|---|---|---|
| Interest accrual (month walk) | `services.py` | `_recompute_contract_status` |
| Rule A month counting | `deps.py` | `months_billed(start, end)` |
| Payment allocation (M1) | `services.py` | Inside `_recompute_contract_status` event loop |
| Receipt "Next Payment" block | `pdf_utils.py` | `build_receipt_pdf` |
| WhatsApp reminder body | `reminders.py` | `build_reminder_body` |
| Payment record (frontend) | `Payments.js` | `submitPayment` / `submitOverdue` |
| Regression tests | `tests/test_iter27_rule_m1.py` | 5 M1 tests |
| Regression (M2 legacy) | `tests/test_iter26_rule_b_hybrid.py` | 6 backwards-compat tests |
| Rule A month tests | `tests/test_iter22_interest_rule.py` | 12 tests |

---

## 3. Quick reference cheat sheet

```
NEW CONTRACT:
    P = L,  U = 0,  interest_rule = "M1"

EACH MONTH ANCHOR (starting Month 2):
    delta = P × R          (Month 1 anchor uses L instead of P)
    U += delta

ANY PAYMENT ARRIVES (M1 partial, interest_only, full):
    take_int  = MIN(amount, U)
    take_princ= MIN(amount - take_int, P)
    U        -= take_int
    P        -= take_princ

NEXT MONTH FORECAST (shown to client):
    next_interest = P × R      (declining balance, principal only)
    new_total_if_unpaid = (P + U) + next_interest
```

---
_Owner: Fatin Penhores Unipessoal, Lda · System version: Feb 2026 · Rule M1_
