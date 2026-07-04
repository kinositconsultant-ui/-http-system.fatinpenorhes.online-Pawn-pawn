import { useEffect, useState } from "react";
import { api, pdfUrl } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../components/ui/dialog";
import { FileText } from "lucide-react";
import { toast } from "sonner";
import { shortInvoice } from "../lib/docNumbers";

export default function Auctions() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(null);
  const [form, setForm] = useState({ sold_price: "", interest_fee: "", tax_percent: "0", buyer_name: "", notes: "" });

  const load = () => api.get("/auctions").then((r) => setRows(r.data));
  useEffect(() => {
    load();
  }, []);

  const openSold = (a) => {
    setCurrent(a);
    setForm({ sold_price: a.starting_price || "", interest_fee: "", tax_percent: "0", buyer_name: "", notes: "" });
    setOpen(true);
  };

  const submitSold = async () => {
    try {
      const payload = {
        sold_price: Number(form.sold_price),
        tax_percent: Number(form.tax_percent || 0),
        buyer_name: form.buyer_name,
        notes: form.notes,
      };
      // Only pass interest_fee if the admin entered one (otherwise backend auto-computes from outstanding interest+penalty)
      if (form.interest_fee !== "" && !Number.isNaN(Number(form.interest_fee))) {
        payload.interest_fee = Number(form.interest_fee);
      }
      await api.post(`/auctions/${current.id}/sold`, payload);
      toast.success("Marked as sold");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="auctions-root">
      <header>
        <div className="text-eyebrow">{t("auctions")}</div>
        <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">{t("auctions")}</h1>
        <p className="text-stone-600 text-sm mt-1">
          Overdue items are moved here from contracts. Mark them as sold to close the loop.
        </p>
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="auctions-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>{t("contract_number")}</Th>
              <Th>{t("item")}</Th>
              <Th right>{t("starting_price")}</Th>
              <Th right>{t("sold_price")}</Th>
              <Th>{t("buyer_name")}</Th>
              <Th>{t("status")}</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50/50">
                <Td className="font-medium whitespace-nowrap">{r.contract_number}</Td>
                <Td className="whitespace-nowrap">
                  <span className="inline-block text-[10px] uppercase tracking-wider text-stone-500 bg-stone-100 border border-stone-200 rounded px-1.5 py-0.5">
                    {r.item_type}
                  </span>
                </Td>
                <Td right className="whitespace-nowrap">${Number(r.starting_price || 0).toLocaleString()}</Td>
                <Td right className="whitespace-nowrap font-medium">{r.sold_price ? `$${Number(r.sold_price).toLocaleString()}` : "—"}</Td>
                <Td className="whitespace-nowrap max-w-[180px] truncate" title={r.buyer_name || ""}>{r.buyer_name || "—"}</Td>
                <Td className="whitespace-nowrap">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border ${
                      r.status === "listed"
                        ? "bg-orange-50 text-orange-800 border-orange-200"
                        : "bg-emerald-50 text-emerald-800 border-emerald-200"
                    }`}
                  >
                    {r.status}
                  </span>
                </Td>
                <Td right>
                  <div className="flex justify-end gap-1.5">
                    {r.status === "listed" && (
                      <button
                        onClick={() => openSold(r)}
                        data-testid={`auction-sold-${r.id}`}
                        className="inline-flex items-center justify-center px-2.5 h-7 rounded-md bg-[#C17767] text-white text-xs font-medium hover:bg-[#A96253] transition-colors whitespace-nowrap"
                        title={t("mark_sold")}
                      >
                        {t("mark_sold")}
                      </button>
                    )}
                    {r.status === "sold" && r.invoice_id && (
                      <a
                        href={pdfUrl(`/invoices/${r.invoice_id}/pdf`)}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={`auction-invoice-${r.id}`}
                        className="inline-flex items-center gap-1 px-2.5 h-7 rounded-md bg-[#DC2626] text-white text-xs font-medium hover:bg-[#B91C1C] transition-colors whitespace-nowrap"
                        title={r.invoice_number}
                      >
                        <FileText className="w-3 h-3" /> {shortInvoice(r.invoice_number) || t("invoice")}
                      </a>
                    )}
                  </div>
                </Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan="7" className="p-8 text-center text-stone-500">
                  No auctions
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("mark_sold")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  {t("sold_price")}
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.sold_price}
                  onChange={(e) => setForm({ ...form, sold_price: e.target.value })}
                  data-testid="auction-sold-price"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Tax % (buyer-facing)
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.tax_percent}
                  onChange={(e) => setForm({ ...form, tax_percent: e.target.value })}
                  data-testid="auction-tax-percent"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">
                {t("interest_fee")} <span className="text-stone-400 normal-case lowercase">(internal — leave blank to auto-compute from contract)</span>
              </Label>
              <Input
                type="number"
                step="0.01"
                placeholder="auto from outstanding interest + penalty"
                value={form.interest_fee}
                onChange={(e) => setForm({ ...form, interest_fee: e.target.value })}
                data-testid="auction-interest-fee"
              />
              <p className="text-[11px] text-stone-500 leading-snug">
                This is the profit portion of the sale. It is added to Net Profit in Finance and is NOT shown on the buyer&apos;s invoice.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">
                {t("buyer_name")}
              </Label>
              <Input
                value={form.buyer_name}
                onChange={(e) => setForm({ ...form, buyer_name: e.target.value })}
                data-testid="auction-buyer-name"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              onClick={submitSold}
              className="bg-[#C17767] hover:bg-[#A96253]"
              data-testid="auction-sold-confirm"
            >
              {t("save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Th({ children, right }) {
  return (
    <th
      className={`px-3 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}
function Td({ children, right, className = "", ...rest }) {
  return <td className={`px-3 py-3 ${right ? "text-right" : ""} ${className}`} {...rest}>{children}</td>;
}
