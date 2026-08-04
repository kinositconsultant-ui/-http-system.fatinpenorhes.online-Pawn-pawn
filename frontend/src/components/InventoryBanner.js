import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import {
  Users,
  Package,
  DollarSign,
  Warehouse,
  Building2,
  Search,
  History,
  Phone,
  Mail,
} from "lucide-react";
import { toast } from "sonner";

const fmtUSD0 = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

/**
 * InventoryBanner
 *
 * Sits above the Items tabs and surfaces:
 *   - Total customers whose items have been received
 *   - Historical count & market value of all items
 *   - Active count & market value (items currently linked to an active
 *     / grace_period / auction_ready contract)
 *   - Warehouse-vs-Office split for ACTIVE items (kind-based: vehicles &
 *     pezadu go to warehouse; electronics go to office)
 *   - Status roll-up (in_stock / pawned / sold / other)
 *
 * Also exposes a search input that resolves to a full "customer history"
 * dossier using /api/history/search.
 */
export default function InventoryBanner() {
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [dossier, setDossier] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get("/inventory/analytics")
      .then((r) => setData(r.data))
      .catch(() => {});
  }, []);

  const doSearch = async () => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const { data: r } = await api.get(
        `/history/search?q=${encodeURIComponent(q.trim())}`
      );
      setDossier(r);
    } catch (e) {
      toast.error(e.response?.data?.detail || "No match");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="inventory-banner">
      {/* Top row: 5 KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <BannerTile
          Icon={Users}
          label="Customers"
          value={data ? data.unique_customers : "…"}
          hint="unique clients on any contract"
          tone="text-[#1B2D5C]"
          bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25"
          testid="ib-customers"
        />
        <BannerTile
          Icon={Package}
          label="Items (Historical)"
          value={data ? data.total_items_all : "…"}
          hint={data ? fmtUSD0(data.total_market_value_all) : ""}
          tone="text-stone-800"
          bg="bg-stone-50 border-stone-300"
          testid="ib-historical"
        />
        <BannerTile
          Icon={DollarSign}
          label="Items (Active)"
          value={data ? data.total_items_active : "…"}
          hint={data ? fmtUSD0(data.total_market_value_active) : ""}
          tone="text-sky-800"
          bg="bg-sky-50 border-sky-200"
          testid="ib-active"
        />
        <BannerTile
          Icon={Warehouse}
          label="Warehouse (Active)"
          value={data ? data.warehouse_active.count : "…"}
          hint={data ? fmtUSD0(data.warehouse_active.market_value) : ""}
          tone="text-[#1B2D5C]"
          bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25"
          testid="ib-warehouse"
        />
        <BannerTile
          Icon={Building2}
          label="Office (Active)"
          value={data ? data.office_active.count : "…"}
          hint={data ? fmtUSD0(data.office_active.market_value) : ""}
          tone="text-emerald-800"
          bg="bg-emerald-50 border-emerald-200"
          testid="ib-office"
        />
      </div>

      {/* Status roll-up strip + history search */}
      <Card className="p-3 md:p-4 border border-stone-200 shadow-none rounded-lg bg-white flex flex-wrap items-center gap-4">
        <div className="flex flex-wrap gap-2 flex-1 min-w-[200px]">
          <StatusPill label="in stock" value={data?.by_status.in_stock} tone="bg-stone-100 text-stone-700 border-stone-300" />
          <StatusPill label="pawned" value={data?.by_status.pawned} tone="bg-sky-100 text-sky-800 border-sky-300" />
          <StatusPill label="redeemed" value={data?.by_status.redeemed} tone="bg-emerald-100 text-emerald-800 border-emerald-300" />
          <StatusPill label="sold" value={data?.by_status.sold} tone="bg-amber-100 text-amber-800 border-amber-300" />
          <StatusPill label="auctioned" value={data?.by_status.auctioned} tone="bg-rose-100 text-rose-800 border-rose-300" />
        </div>
        <div className="flex items-end gap-2">
          <div>
            <Label className="text-xs uppercase tracking-wider text-stone-500">
              Customer history search
            </Label>
            <div className="relative">
              <Search className="absolute left-2 top-2.5 w-4 h-4 text-stone-400" />
              <Input
                className="pl-8 w-64"
                placeholder="Contract # · item id · name · phone"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doSearch()}
                data-testid="history-search-input"
              />
            </div>
          </div>
          <Button
            className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
            onClick={doSearch}
            disabled={loading}
            data-testid="history-search-btn"
          >
            {loading ? "…" : <History className="w-4 h-4" />}
          </Button>
        </div>
      </Card>

      {/* Dossier dialog */}
      <Dialog open={!!dossier} onOpenChange={(o) => !o && setDossier(null)}>
        <DialogContent className="max-w-5xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="w-5 h-5 text-[#1B2D5C]" />
              Customer History
              {dossier?.match && (
                <span className="text-[11px] font-normal px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200 text-stone-600">
                  matched by {dossier.match}: {dossier.matched_value}
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          {dossier && dossier.client && (
            <DossierBody dossier={dossier} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BannerTile({ Icon, label, value, hint, tone, bg, testid }) {
  return (
    <div className={`rounded-lg border ${bg} p-3 md:p-4`} data-testid={testid}>
      <div className="flex items-center gap-2">
        <Icon className={`w-4 h-4 ${tone}`} />
        <span className="text-[11px] uppercase tracking-wide text-stone-500">
          {label}
        </span>
      </div>
      <div className={`font-display text-xl md:text-2xl font-semibold mt-1 ${tone}`}>
        {value}
      </div>
      {hint && <div className="text-[11px] text-stone-500 mt-0.5">{hint}</div>}
    </div>
  );
}

function StatusPill({ label, value, tone }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-xs font-medium ${tone}`}
    >
      {label}
      <span className="ml-1 tabular-nums">{value ?? "…"}</span>
    </span>
  );
}

function DossierBody({ dossier }) {
  const { client, contracts, payments, inspections, items, totals } = dossier;
  return (
    <div className="space-y-4 text-sm">
      {/* Client header */}
      <div className="rounded-md border border-stone-200 bg-stone-50 p-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="text-eyebrow">Client</div>
            <div className="text-xl font-semibold">{client.full_name}</div>
            <div className="text-xs text-stone-500 mt-0.5">
              {client.id_type} {client.id_number}
            </div>
          </div>
          <div className="text-xs text-stone-600 space-y-0.5">
            {client.phone && (
              <div className="flex items-center gap-1">
                <Phone className="w-3 h-3" /> {client.phone}
              </div>
            )}
            {client.email && (
              <div className="flex items-center gap-1">
                <Mail className="w-3 h-3" /> {client.email}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Totals row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
        <MiniTile label="Contracts" value={totals.contracts_total} />
        <MiniTile label="Active" value={totals.contracts_active} tone="text-sky-700" />
        <MiniTile label="Redeemed" value={totals.contracts_redeemed} tone="text-emerald-700" />
        <MiniTile label="Total borrowed" value={fmtUSD0(totals.total_borrowed)} />
        <MiniTile label="Total paid" value={fmtUSD0(totals.total_paid)} tone="text-emerald-700" />
        <MiniTile label="Inspections" value={totals.inspections_total} />
      </div>

      <Section title="Contracts" count={contracts.length} testid="dossier-contracts">
        <table className="min-w-full text-xs">
          <thead className="bg-stone-50 text-left">
            <tr>
              <MiniTh>Contract</MiniTh>
              <MiniTh>Item</MiniTh>
              <MiniTh>Start</MiniTh>
              <MiniTh>Due</MiniTh>
              <MiniTh right>Loan</MiniTh>
              <MiniTh right>Remaining</MiniTh>
              <MiniTh>Status</MiniTh>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c) => (
              <tr key={c.id} className="border-t border-stone-100">
                <MiniTd className="font-mono">{c.contract_number}</MiniTd>
                <MiniTd>{c.item_type}</MiniTd>
                <MiniTd>{c.contract_date}</MiniTd>
                <MiniTd>{c.due_date}</MiniTd>
                <MiniTd right>{fmtUSD0(c.loan_amount)}</MiniTd>
                <MiniTd right>{fmtUSD0(c.principal_remaining)}</MiniTd>
                <MiniTd>
                  <span className="px-1.5 py-0.5 rounded-full bg-stone-100 border border-stone-200 text-[10px]">
                    {c.status}
                  </span>
                </MiniTd>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Items pawned" count={items.length} testid="dossier-items">
        <table className="min-w-full text-xs">
          <thead className="bg-stone-50 text-left">
            <tr>
              <MiniTh>Kind</MiniTh>
              <MiniTh>Brand · Model</MiniTh>
              <MiniTh>Plate / Serial</MiniTh>
              <MiniTh right>Market $</MiniTh>
              <MiniTh>Location</MiniTh>
              <MiniTh>Contract status</MiniTh>
            </tr>
          </thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={`${it.id}-${i}`} className="border-t border-stone-100">
                <MiniTd>{it.kind}</MiniTd>
                <MiniTd>
                  {it.brand} · {it.model}
                </MiniTd>
                <MiniTd className="font-mono">
                  {it.plate || it.serial || "—"}
                </MiniTd>
                <MiniTd right>{fmtUSD0(it.market_value)}</MiniTd>
                <MiniTd>{it.location || "—"}</MiniTd>
                <MiniTd>
                  <span className="px-1.5 py-0.5 rounded-full bg-stone-100 border border-stone-200 text-[10px]">
                    {it.contract_status || "—"}
                  </span>
                </MiniTd>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Payments" count={payments.length} testid="dossier-payments">
        <table className="min-w-full text-xs">
          <thead className="bg-stone-50 text-left">
            <tr>
              <MiniTh>Date</MiniTh>
              <MiniTh>Receipt</MiniTh>
              <MiniTh>Contract</MiniTh>
              <MiniTh>Type</MiniTh>
              <MiniTh right>Amount</MiniTh>
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id} className="border-t border-stone-100">
                <MiniTd>{p.date}</MiniTd>
                <MiniTd className="font-mono">{p.receipt_number}</MiniTd>
                <MiniTd className="font-mono">{p.contract_number}</MiniTd>
                <MiniTd>
                  <span
                    className={`px-1.5 py-0.5 rounded-full border text-[10px] ${
                      p.type === "disbursement"
                        ? "bg-blue-100 text-blue-900 border-blue-300"
                        : "bg-stone-100 text-stone-700 border-stone-200"
                    }`}
                  >
                    {p.type}
                  </span>
                </MiniTd>
                <MiniTd right>{fmtUSD0(p.amount)}</MiniTd>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {inspections.length > 0 && (
        <Section
          title="Inspections"
          count={inspections.length}
          testid="dossier-inspections"
        >
          <table className="min-w-full text-xs">
            <thead className="bg-stone-50 text-left">
              <tr>
                <MiniTh>Date</MiniTh>
                <MiniTh>Contract</MiniTh>
                <MiniTh>Category</MiniTh>
                <MiniTh right>Amount</MiniTh>
                <MiniTh>Reimbursed?</MiniTh>
              </tr>
            </thead>
            <tbody>
              {inspections.map((i) => (
                <tr key={i.id} className="border-t border-stone-100">
                  <MiniTd>{i.incurred_date}</MiniTd>
                  <MiniTd className="font-mono">{i.contract_number}</MiniTd>
                  <MiniTd>{i.category}</MiniTd>
                  <MiniTd right>{fmtUSD0(i.amount)}</MiniTd>
                  <MiniTd>
                    {i.reimbursed ? (
                      <span className="text-emerald-700">yes ({fmtUSD0(i.reimbursed_amount)})</span>
                    ) : (
                      <span className="text-amber-700">pending</span>
                    )}
                  </MiniTd>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
    </div>
  );
}

function Section({ title, count, testid, children }) {
  return (
    <div className="rounded-md border border-stone-200 overflow-hidden" data-testid={testid}>
      <div className="px-3 py-2 bg-stone-50 border-b border-stone-200 flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-stone-600 font-semibold">
          {title}
        </span>
        <span className="text-[10px] text-stone-500">{count} row(s)</span>
      </div>
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

function MiniTile({ label, value, tone = "text-stone-800" }) {
  return (
    <div className="rounded-md border border-stone-200 bg-white p-2">
      <div className="text-[10px] uppercase tracking-wide text-stone-500">
        {label}
      </div>
      <div className={`font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function MiniTh({ children, right }) {
  return (
    <th
      className={`px-2 py-1 text-[10px] uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}

function MiniTd({ children, right, className = "" }) {
  return (
    <td
      className={`px-2 py-1 whitespace-nowrap ${right ? "text-right" : ""} ${className}`}
    >
      {children}
    </td>
  );
}
