import { useEffect, useState } from "react";
import { api, pdfUrl } from "../lib/api";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { CheckCircle2, PackageCheck, Clock, FileText, FileSpreadsheet } from "lucide-react";
import { toast } from "sonner";
import PdfPreviewDialog from "./PdfPreviewDialog";

const usd = (n) => `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Business Dashboard: contracts fully paid in a month + interest each one earned.
export default function ClosedContractsCard() {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [data, setData] = useState(null);
  const [preview, setPreview] = useState(false);

  useEffect(() => {
    let alive = true;
    api.get(`/business/closed-contracts?month=${month}`).then((r) => alive && setData(r.data)).catch(() => alive && setData({ rows: [], count: 0 }));
    return () => { alive = false; };
  }, [month]);

  const downloadCsv = async () => {
    try {
      const r = await api.get(`/business/closed-contracts/export/csv?month=${month}`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "text/csv" }));
      const a = Object.assign(document.createElement("a"), { href: url, download: `closed-contracts-${month}.csv` });
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) {
      toast.error(e.response?.data?.detail || "CSV export failed");
    }
  };

  return (
    <Card className="p-4 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="closed-contracts-card">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-700" />
          <div className="text-eyebrow">Closed this month</div>
        </div>
        <div className="flex items-center gap-1.5">
          <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="h-8 w-40 text-xs" data-testid="closed-month" />
          <Button type="button" size="sm" className="h-8 px-2 bg-[#B91C1C] hover:bg-[#991B1B] text-white" onClick={() => setPreview(true)} title="PDF for accountant" data-testid="closed-pdf-btn">
            <FileText className="w-4 h-4" />
          </Button>
          <Button type="button" size="sm" className="h-8 px-2 bg-emerald-700 hover:bg-emerald-800 text-white" onClick={downloadCsv} title="CSV export" data-testid="closed-csv-btn">
            <FileSpreadsheet className="w-4 h-4" />
          </Button>
        </div>
      </div>
      {data && (
        <div className="grid grid-cols-3 gap-2 mb-3">
          {[["Contracts", data.count, ""], ["Interest earned", usd(data.interest_total), "text-emerald-800"], ["Penalties", usd(data.penalty_total), "text-amber-800"]].map(([l, v, tone]) => (
            <div key={l} className="rounded-md bg-stone-50 border border-stone-200 p-2">
              <div className="text-[10px] uppercase tracking-wider text-stone-500">{l}</div>
              <div className={`font-display text-lg ${tone}`} data-testid={`closed-kpi-${l.toLowerCase().replace(/\s/g, "-")}`}>{v}</div>
            </div>
          ))}
        </div>
      )}
      <div className="max-h-72 overflow-y-auto divide-y divide-stone-100" data-testid="closed-rows">
        {data?.rows?.length === 0 && <div className="text-sm text-stone-400 py-6 text-center">No contracts closed in this month.</div>}
        {(data?.rows || []).map((r) => (
          <div key={r.id} className="py-2 flex items-center gap-3 text-xs" data-testid={`closed-row-${r.id}`}>
            <div className="flex-1 min-w-0">
              <div className="font-mono text-[11px] text-stone-500">{r.contract_number} · {r.item_type}</div>
              <div className="font-medium truncate">{r.client_name || "—"}</div>
              <div className="text-stone-500">Loan {usd(r.loan_amount)} · closed {r.closed_on}</div>
            </div>
            <div className="text-right shrink-0">
              <div className="font-semibold text-emerald-800">+{usd(r.interest_earned)}</div>
              {r.penalty_earned > 0 && <div className="text-amber-800">pen. {usd(r.penalty_earned)}</div>}
              <div className={`inline-flex items-center gap-1 text-[10px] ${r.item_released ? "text-teal-700" : "text-stone-500"}`}>
                {r.item_released ? <PackageCheck className="w-3 h-3" /> : <Clock className="w-3 h-3" />} {r.item_released ? "released" : "awaiting pickup"}
              </div>
            </div>
          </div>
        ))}
      </div>
      <PdfPreviewDialog open={preview} onOpenChange={setPreview} url={pdfUrl(`/business/closed-contracts/export/pdf?month=${month}`)} title={`Closed contracts · ${month}`} downloadName={`closed-contracts-${month}.pdf`} />
    </Card>
  );
}
