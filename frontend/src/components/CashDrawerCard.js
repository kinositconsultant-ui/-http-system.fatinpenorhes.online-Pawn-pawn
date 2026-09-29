import { useEffect, useState } from "react";
import { api, pdfUrl } from "../lib/api";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Wallet, FileText, CheckSquare, Square } from "lucide-react";
import { toast } from "sonner";
import PdfPreviewDialog from "./PdfPreviewDialog";

const usd = (n) => `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Finance → daily cash-drawer reconciliation (received / change returned / pending change).
export default function CashDrawerCard() {
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const [preview, setPreview] = useState(false);

  const load = () => api.get(`/finance/cash-drawer?date=${day}`).then((r) => setData(r.data)).catch(() => setData(null));
  useEffect(() => { load(); }, [day]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleReturned = async (r) => {
    try {
      await api.post(`/payments/${r.id}/change-returned?returned=${!r.change_returned}`);
      toast.success(r.change_returned ? "Marked as pending" : "Change marked as returned");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const t = data?.totals || {};
  const tiles = [
    ["Cash received", usd(t.cash_in), "text-emerald-800", "received"],
    ["Change owed", usd(t.change_owed), "text-stone-800", "owed"],
    ["Change returned", usd(t.change_returned), "text-teal-700", "returned"],
    ["Change pending", usd(t.change_pending), t.change_pending > 0 ? "text-amber-700" : "text-stone-800", "pending"],
    ["Loans disbursed", usd(t.disbursed_out), "text-rose-700", "disbursed"],
    ["Net in drawer", usd(t.net_drawer), "text-[#1B2D5C]", "net"],
  ];

  return (
    <Card className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-4" data-testid="cash-drawer-card">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Wallet className="w-5 h-5 text-[#1B2D5C]" />
          <h2 className="font-display text-xl">Cash Drawer</h2>
          <span className="text-xs text-stone-500">{t.receipts ?? 0} receipts</span>
        </div>
        <div className="flex items-center gap-2">
          <Input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="h-8 w-40 text-xs" data-testid="drawer-date" />
          <Button type="button" size="sm" className="h-8 bg-[#B91C1C] hover:bg-[#991B1B] text-white" onClick={() => setPreview(true)} data-testid="drawer-pdf-btn">
            <FileText className="w-4 h-4 mr-1" /> PDF
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {tiles.map(([l, v, tone, id]) => (
          <div key={l} className="rounded-md bg-stone-50 border border-stone-200 p-2.5">
            <div className="text-[10px] uppercase tracking-wider text-stone-500">{l}</div>
            <div className={`font-display text-lg ${tone}`} data-testid={`drawer-kpi-${id}`}>{v}</div>
          </div>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="drawer-table">
          <thead className="bg-stone-50 text-left text-[10px] uppercase tracking-wider text-stone-500">
            <tr><th className="px-3 py-2">Receipt</th><th className="px-3 py-2">Time</th><th className="px-3 py-2">Client</th><th className="px-3 py-2">Type</th><th className="px-3 py-2 text-right">Amount</th><th className="px-3 py-2 text-right">Change</th><th className="px-3 py-2">Returned</th></tr>
          </thead>
          <tbody>
            {(data?.rows || []).length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-stone-400" data-testid="drawer-empty">No receipts on this day.</td></tr>}
            {(data?.rows || []).map((r) => (
              <tr key={r.id} className="border-t border-stone-100" data-testid={`drawer-row-${r.id}`}>
                <td className="px-3 py-2 font-mono text-xs">{r.receipt_number}</td>
                <td className="px-3 py-2 text-xs text-stone-500">{(r.created_at || "").slice(11, 16)}</td>
                <td className="px-3 py-2 text-xs"><div className="font-medium">{r.client_name || "—"}</div><div className="text-stone-500 font-mono text-[10px]">{r.contract_number}</div></td>
                <td className="px-3 py-2 text-xs capitalize">{(r.type || "").replace(/_/g, " ")}</td>
                <td className="px-3 py-2 text-right font-medium">{usd(r.amount)}</td>
                <td className="px-3 py-2 text-right text-xs">{r.overpaid > 0 ? usd(r.overpaid) : "—"}</td>
                <td className="px-3 py-2">
                  {r.overpaid > 0 && (
                    <button type="button" onClick={() => toggleReturned(r)} className={`inline-flex items-center gap-1 text-xs ${r.change_returned ? "text-teal-700" : "text-amber-700"}`} data-testid={`drawer-returned-${r.id}`}>
                      {r.change_returned ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                      {r.change_returned ? `Yes · ${r.change_returned_by || ""}` : "Pending"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PdfPreviewDialog open={preview} onOpenChange={setPreview} url={pdfUrl(`/finance/cash-drawer/export/pdf?date=${day}`)} title={`Cash Drawer · ${day}`} downloadName={`cash-drawer-${day}.pdf`} />
    </Card>
  );
}
