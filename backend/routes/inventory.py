"""Inventory analytics & customer history search (iter 63 · Phase G).

Endpoints:

  GET /api/inventory/analytics
      Aggregate KPI tiles for the Items page:
        - Total customers whose items have been received (unique client_ids
          on any contract)
        - Complete count/market value of every item ever recorded (historical)
        - Active items + market value (items currently linked to an active,
          grace_period, or auction_ready contract)
        - Breakdown by status (in_stock / pawned / sold / redeemed / auction)
        - Warehouse-vs-office split for ACTIVE items:
            warehouse = cars + motorcycles + pezadu on active contracts
            office    = electronics on active contracts
          Also derives a `location_warehouse` / `location_office` sub-split
          from the `location` free-text field (case-insensitive keyword scan).

  GET /api/history/search?q=<term>
      Multi-purpose lookup used by the "customer history" search on the
      Items page. Matches on:
        - contract_number (exact or prefix)
        - item id (any collection)
        - client id / phone / full_name (partial, case-insensitive)
      Returns a single client dossier with:
        - client info
        - every contract (past + present) with dates, status, principal
        - every payment
        - every item they've ever pawned
        - every inspection expense tied to any of their contracts
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import db, get_current_user, COLLECTION_MAP

router = APIRouter(tags=["inventory"])

ACTIVE_CONTRACT_STATUSES = {"active", "grace_period", "overdue", "auction_ready"}
WAREHOUSE_KINDS = ("car", "motorcycle", "pezadu")
OFFICE_KINDS = ("electronic",)
ALL_KINDS = WAREHOUSE_KINDS + OFFICE_KINDS


def _is_warehouse_location(loc: str) -> bool:
    if not loc:
        return False
    return "warehouse" in loc.lower() or "armazém" in loc.lower() or "armazen" in loc.lower()


def _is_office_location(loc: str) -> bool:
    if not loc:
        return False
    return "office" in loc.lower() or "shop" in loc.lower() or "eskritóriu" in loc.lower() or "eskritoriu" in loc.lower()


@router.get("/inventory/analytics")
async def inventory_analytics(_: dict = Depends(get_current_user)):
    # Fetch all contracts once; we need this both for status lookups and for
    # counting unique customers.
    contracts = await db.contracts.find(
        {}, {"_id": 0, "id": 1, "item_id": 1, "item_type": 1, "client_id": 1, "status": 1}
    ).to_list(20000)
    active_item_ids: set[str] = set()
    unique_customers: set[str] = set()
    contracts_by_status: dict[str, int] = {}
    for c in contracts:
        st = c.get("status") or "active"
        contracts_by_status[st] = contracts_by_status.get(st, 0) + 1
        if c.get("client_id"):
            unique_customers.add(c["client_id"])
        if st in ACTIVE_CONTRACT_STATUSES and c.get("item_id"):
            active_item_ids.add(c["item_id"])

    # Walk every item collection and compute totals.
    totals = {
        "count_all": 0,
        "market_value_all": 0.0,
        "count_active": 0,
        "market_value_active": 0.0,
    }
    by_kind: dict[str, dict] = {}
    warehouse = {"count_active": 0, "market_value_active": 0.0,
                 "count_location_warehouse": 0, "market_value_location_warehouse": 0.0}
    office = {"count_active": 0, "market_value_active": 0.0,
              "count_location_office": 0, "market_value_location_office": 0.0}
    by_status = {"in_stock": 0, "pawned": 0, "redeemed": 0, "sold": 0, "auctioned": 0, "other": 0}

    for kind in ALL_KINDS:
        coll = db[COLLECTION_MAP[kind]]
        kbucket = {"count_all": 0, "market_value_all": 0.0,
                   "count_active": 0, "market_value_active": 0.0}
        async for it in coll.find({}, {"_id": 0}):
            v = float(it.get("market_value", 0) or 0)
            kbucket["count_all"] += 1
            kbucket["market_value_all"] += v
            totals["count_all"] += 1
            totals["market_value_all"] += v

            st = (it.get("status") or "in_stock").lower()
            if st in by_status:
                by_status[st] += 1
            else:
                by_status["other"] += 1

            is_active = it.get("id") in active_item_ids
            if is_active:
                kbucket["count_active"] += 1
                kbucket["market_value_active"] += v
                totals["count_active"] += 1
                totals["market_value_active"] += v
                # Warehouse-vs-office by kind rule
                if kind in WAREHOUSE_KINDS:
                    warehouse["count_active"] += 1
                    warehouse["market_value_active"] += v
                else:
                    office["count_active"] += 1
                    office["market_value_active"] += v
                # Location-based split (secondary signal from `location` field)
                loc = it.get("location") or ""
                if _is_warehouse_location(loc):
                    warehouse["count_location_warehouse"] += 1
                    warehouse["market_value_location_warehouse"] += v
                elif _is_office_location(loc):
                    office["count_location_office"] += 1
                    office["market_value_location_office"] += v

        by_kind[kind] = {k: round(v, 2) if isinstance(v, float) else v for k, v in kbucket.items()}

    return {
        "unique_customers": len(unique_customers),
        "total_items_all": totals["count_all"],
        "total_market_value_all": round(totals["market_value_all"], 2),
        "total_items_active": totals["count_active"],
        "total_market_value_active": round(totals["market_value_active"], 2),
        "by_kind": by_kind,
        "by_status": by_status,
        "warehouse_active": {
            "count": warehouse["count_active"],
            "market_value": round(warehouse["market_value_active"], 2),
            "count_by_location_tag": warehouse["count_location_warehouse"],
            "market_value_by_location_tag": round(warehouse["market_value_location_warehouse"], 2),
        },
        "office_active": {
            "count": office["count_active"],
            "market_value": round(office["market_value_active"], 2),
            "count_by_location_tag": office["count_location_office"],
            "market_value_by_location_tag": round(office["market_value_location_office"], 2),
        },
        "contracts_by_status": contracts_by_status,
    }


async def _client_dossier(client_id: str) -> dict:
    client = await db.clients.find_one({"id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    contracts = await db.contracts.find(
        {"client_id": client_id}, {"_id": 0}
    ).sort("contract_date", -1).to_list(1000)
    cids = [c["id"] for c in contracts]
    payments = await db.payments.find(
        {"contract_id": {"$in": cids}}, {"_id": 0}
    ).sort("date", -1).to_list(3000)
    inspections = await db.inspections.find(
        {"contract_id": {"$in": cids}}, {"_id": 0}
    ).sort("incurred_date", -1).to_list(2000)

    # Resolve items referenced by contracts.
    items: list[dict] = []
    for c in contracts:
        kind = c.get("item_type")
        iid = c.get("item_id")
        if kind in COLLECTION_MAP and iid:
            it = await db[COLLECTION_MAP[kind]].find_one({"id": iid}, {"_id": 0})
            if it:
                items.append({**it, "kind": kind, "contract_id": c["id"],
                              "contract_number": c.get("contract_number"),
                              "contract_status": c.get("status")})

    # Roll up totals for header ribbons
    total_borrowed = sum(float(c.get("loan_amount", 0) or 0) for c in contracts)
    total_paid = sum(
        float(p.get("amount", 0) or 0) for p in payments
        if p.get("type") != "disbursement"
    )
    redeemed_count = sum(1 for c in contracts if c.get("status") == "redeemed")
    active_count = sum(
        1 for c in contracts if c.get("status") in ACTIVE_CONTRACT_STATUSES
    )
    return {
        "client": client,
        "contracts": contracts,
        "payments": payments,
        "inspections": inspections,
        "items": items,
        "totals": {
            "contracts_total": len(contracts),
            "contracts_active": active_count,
            "contracts_redeemed": redeemed_count,
            "total_borrowed": round(total_borrowed, 2),
            "total_paid": round(total_paid, 2),
            "items_pawned": len(items),
            "inspections_total": len(inspections),
        },
    }


@router.get("/history/search")
async def history_search(
    q: str = Query(..., min_length=1, description="Contract number, item id, client id/name/phone"),
    _: dict = Depends(get_current_user),
):
    """Fuzzy lookup that resolves to a single client dossier.

    Lookup order:
      1. Exact contract_number match
      2. Exact item id in any items collection → contract → client
      3. Exact client id match
      4. Partial match on client full_name / phone / email
    """
    q = q.strip()
    # 1. contract number (case-insensitive prefix)
    contract = await db.contracts.find_one(
        {"contract_number": {"$regex": f"^{q}$", "$options": "i"}}, {"_id": 0}
    )
    if not contract:
        # Prefix match if no exact
        contract = await db.contracts.find_one(
            {"contract_number": {"$regex": f"^{q}", "$options": "i"}}, {"_id": 0}
        )
    if contract and contract.get("client_id"):
        return {"match": "contract_number", "matched_value": contract["contract_number"],
                **await _client_dossier(contract["client_id"])}

    # 2. item id in any items collection
    for kind in ALL_KINDS:
        it = await db[COLLECTION_MAP[kind]].find_one({"id": q}, {"_id": 0, "id": 1})
        if it:
            c = await db.contracts.find_one({"item_id": q}, {"_id": 0})
            if c and c.get("client_id"):
                return {"match": "item_id", "matched_value": q, "item_kind": kind,
                        **await _client_dossier(c["client_id"])}
            return {"match": "item_id_orphan", "matched_value": q, "item_kind": kind,
                    "detail": "Item exists but is not linked to any contract"}

    # 3. exact client id
    client = await db.clients.find_one({"id": q}, {"_id": 0, "id": 1})
    if client:
        return {"match": "client_id", "matched_value": q, **await _client_dossier(q)}

    # 4. partial client
    partial = await db.clients.find_one(
        {"$or": [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"id_number": {"$regex": q, "$options": "i"}},
        ]},
        {"_id": 0, "id": 1, "full_name": 1},
    )
    if partial:
        return {"match": "client_partial", "matched_value": partial.get("full_name"),
                **await _client_dossier(partial["id"])}

    raise HTTPException(status_code=404, detail=f"No match for '{q}'")


@router.get("/history/client/{client_id}")
async def history_by_client(client_id: str, _: dict = Depends(get_current_user)):
    """Direct dossier lookup by client id (used when the UI already knows who to load)."""
    return await _client_dossier(client_id)
