import os, requests

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].strip()
s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": "admin@fatinpenhores.tl", "password": "admin123"}, timeout=15)
r.raise_for_status()

def get(path):
    return s.get(f"{BASE}/api{path}", timeout=60)

contracts = get("/contracts").json()
cid = contracts[0]["id"]
# contract with payments (for summary)
pmts = get("/payments").json()
pay = next(p for p in pmts if p.get("type") != "disbursement")
pid, pcid = pay["id"], pay["contract_id"]
clients = get("/clients").json()
clid = clients[0]["id"]
inv = get("/invoices").json()
iid = inv[0]["id"] if inv else None
fs = get("/funding-sources").json()
sid = (fs[0]["id"] if isinstance(fs, list) and fs else None)

tests = [
    ("Contract PDF", f"/contracts/{cid}/pdf"),
    ("Contract label", f"/contracts/{cid}/label-pdf"),
    ("Bulk labels", "/contracts/labels-pdf"),
    ("Auction agreement", f"/contracts/{cid}/auction-agreement-pdf"),
    ("Payments summary (history)", f"/contracts/{pcid}/payments-summary-pdf"),
    ("Payment receipt EN", f"/payments/{pid}/pdf?lang=en"),
    ("Payment receipt TET", f"/payments/{pid}/pdf?lang=tet"),
    ("Auction catalogue", "/auctions/catalogue/pdf"),
    ("Public catalogue", "/public/auction-catalogue/pdf"),
    ("Client member card", f"/clients/{clid}/card-pdf"),
    ("Dashboard snapshot", "/dashboard/snapshot/pdf"),
    ("Rules print card", "/rules/print-card"),
    ("Migration audit penalty", "/migration-audit/penalty/pdf"),
    ("Finance summary", "/finance/summary/export/pdf"),
    ("Finance auction report", "/finance/auction-report/pdf"),
    ("Capital sources", "/finance/capital-sources/export/pdf"),
    ("Expenses export", "/finance/expenses/export/pdf"),
    ("Audit log export", "/audit-log/export/pdf"),
    ("Invoices list export", "/invoices/export/pdf"),
]
if iid:
    tests.append(("Invoice PDF", f"/invoices/{iid}/pdf"))
if sid:
    tests.append(("Amortization", f"/funding-sources/{sid}/amortization-pdf"))
for tab in ["contracts", "payments", "overdue", "auctions", "clients"]:
    tests.append((f"Report v2 {tab}", f"/reports/v2/{tab}/export?format=pdf"))

fails = []
for name, path in tests:
    try:
        r = get(path)
        ok = r.status_code == 200 and r.content[:4] == b"%PDF"
        size = len(r.content)
        print(f"{'PASS' if ok else 'FAIL'}  {name:32s} {r.status_code} {size:>8}B  {path}")
        if not ok:
            fails.append((name, path, r.status_code, r.text[:200] if r.headers.get('content-type','').startswith('application/json') else r.content[:80]))
    except Exception as e:
        print(f"FAIL  {name:32s} EXC {e}")
        fails.append((name, path, "EXC", str(e)))

print("\n=== FAILURES ===" if fails else "\n=== ALL PASS ===")
for f in fails:
    print(f)
