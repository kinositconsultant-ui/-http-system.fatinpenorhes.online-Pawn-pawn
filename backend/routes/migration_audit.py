"""Data Migration Audit — Nov-2026 Contracts Overhaul.

One-off admin report showing every contract's OLD vs NEW penalty calculation.
- Old rule: `penalty = original_loan × penalty_rate`
- New rule: `penalty = current_principal × penalty_rate` (Nov-2026 spec)

The delta is the auditor-visible dollar amount each client should NO LONGER
be charged on top of principal they've already paid down.

Endpoints:
  GET /api/migration-audit/penalty       → JSON payload
  GET /api/migration-audit/penalty/pdf   → Branded PDF for the auditor
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from deps import db, require_admin
from services import _recompute_contract_status
from pdf_utils import build_report_pdf

router = APIRouter()


async def _build_penalty_audit_rows() -> list[dict]:
    """Return one row per contract with a non-zero penalty delta.

    A row is included if it's overdue AND the client has paid down some
    principal — those are the contracts where the old vs new penalty differs.
    """
    contracts = await db.contracts.find({}, {"_id": 0}).to_list(5000)
    rows: list[dict] = []
    for c in contracts:
        await _recompute_contract_status(c)
        if c.get("status") not in ("overdue", "grace_period", "auction_ready"):
            continue
        original = float(c.get("original_loan_amount") or c.get("loan_amount") or 0)
        current = float(c.get("current_principal", c.get("principal_remaining", 0)) or 0)
        rate = float(c.get("penalty_rate", 10.0))
        old_penalty = round(original * rate / 100.0, 2)
        new_penalty = round(current * rate / 100.0, 2)
        delta = round(new_penalty - old_penalty, 2)
        if abs(delta) < 0.01:
            continue  # no change → skip
        rows.append({
            "contract_number": c.get("contract_number"),
            "contract_date": c.get("contract_date"),
            "status": c.get("status"),
            "original_loan_amount": original,
            "current_principal": current,
            "principal_paid": round(original - current, 2),
            "old_penalty": old_penalty,
            "new_penalty": new_penalty,
            "penalty_delta": delta,
        })
    # Sort by absolute delta desc so the biggest corrections show first
    rows.sort(key=lambda r: abs(r["penalty_delta"]), reverse=True)
    return rows


@router.get("/migration-audit/penalty")
async def penalty_audit(_: dict = Depends(require_admin)):
    rows = await _build_penalty_audit_rows()
    total_old = round(sum(r["old_penalty"] for r in rows), 2)
    total_new = round(sum(r["new_penalty"] for r in rows), 2)
    total_delta = round(sum(r["penalty_delta"] for r in rows), 2)
    return {
        "kpis": {
            "contracts_affected": len(rows),
            "old_total_penalty": total_old,
            "new_total_penalty": total_new,
            "penalty_delta_total": total_delta,
        },
        "columns": [
            "contract_number", "contract_date", "status",
            "original_loan_amount", "current_principal", "principal_paid",
            "old_penalty", "new_penalty", "penalty_delta",
        ],
        "rows": rows,
    }


@router.get("/migration-audit/penalty/pdf")
async def penalty_audit_pdf(admin: dict = Depends(require_admin)):
    data = await penalty_audit(admin)  # type: ignore[arg-type]
    pdf = build_report_pdf("Nov-2026 Penalty Migration Audit", data)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="penalty-migration-audit.pdf"',
            "X-Contracts-Affected": str(data["kpis"]["contracts_affected"]),
        },
    )
