import { useEffect, useMemo, useState, Fragment } from "react";
import { api, pdfUrl } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import { FileText, Trash2, ChevronDown, ChevronRight, Eye } from "lucide-react";
import { toast } from "sonner";
import { shortInvoice } from "../lib/docNumbers";
import PdfPreviewDialog from "../components/PdfPreviewDialog";

export default function Auctions() {
  const { t } = useLang();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(null);
  const [form, setForm] = useState({ sold_price: "", interest_fee: "", tax_percent: "0", buyer_name: "", notes: "" });
  const [expanded, setExpanded] = useState({}); // { clientKey: true }
  const [pdfPreview, setPdfPreview] = useState({ open: false, url: "", title: "", filename: "" });

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

  const deleteAuction = async (a) => {
    const label = a.contract_number || a.id;
    const extra = a.status === "sold"
      ? "\nThis auction is already SOLD — deleting it will not remove the invoice or reverse the sale, but the record will disappear from this list."
      : "\nThe underlying contract will revert to 'overdue' so you can re-list or reactivate it.";
    if (!window.confirm(`Delete auction ${label}?${extra}`)) return;
    try {
      await api.delete(`/auctions/${a.id}`);
      toast.success("Auction deleted");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const previewInvoice = (a) => {
    if (!a.invoice_id) return;
    setPdfPreview({
      open: true,
      url: pdfUrl(`/invoices/${a.invoice_id}/pdf`),
      title: `${t("invoice")} ${shortInvoice(a.invoice_number) || a.invoice_number}`,
      filename: `${a.invoice_number || "invoice"}.pdf`,
    });
  };

  // Group auctions by client_name so the same pawner is shown once per row
  // and their items can be expanded on demand.
  const groups = useMemo(() => {
    const map = new Map();
    for (const r of rows) {
      const key = r.client_name || "—";
      const g = map.get(key) || {
        client_name: key,
        client_id: r.client_id || null,
        items: [],
      };
      g.items.push(r);
      map.set(key, g);
    }
    return Array.from(map.values());
  }, [rows]);

  const toggle = (key) =>
    setExpanded((e) => ({ ...e, [key]: !e[key] }));

  const statusPill = (status) =>
    status === "listed"
      ? "bg-orange-50 text-orange-800 border-orange-200"
      : status === "sold"
      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
      : "bg-stone-100 text-stone-700 border-stone-200";

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
              <Th className="w-10"></Th>
              <Th>{t("client_name") || "Client"}</Th>
              <Th right>Items</Th>
              <Th right>Listed</Th>
              <Th right>Sold</Th>
              <Th right>Total Sold Price</Th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => {
              const key = `${g.client_id || `orphan-${g.items[0]?.id || g.client_name}`}`;
              const isOpen = !!expanded[key];
              const listed = g.items.filter((i) => i.status === "listed").length;
              const sold = g.items.filter((i) => i.status === "sold").length;
              const totalSold = g.items.reduce((s, i) => s + Number(i.sold_price || 0), 0);
              return (
                <Fragment key={key}>
                  <tr
                    key={`grp-${key}`}
                    className="border-t border-stone-100 hover:bg-stone-50/50 cursor-pointer"
                    onClick={() => toggle(key)}
                    data-testid={`auction-group-${key}`}
                  >
                    <Td>
                      <button
                        type="button"
                        className="inline-flex items-center justify-center w-6 h-6 rounded-md hover:bg-stone-200"
                        aria-label={isOpen ? "Collapse" : "Expand"}
                        data-testid={`auction-group-toggle-${key}`}
                      >
                        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </button>
                    </Td>
                    <Td className="font-medium">{g.client_name}</Td>
                    <Td right className="tabular-nums">{g.items.length}</Td>
                    <Td right>
                      {listed > 0 ? (
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${statusPill("listed")}`}>
                          {listed}
                        </span>
                      ) : <span className="text-stone-400">—</span>}
                    </Td>
                    <Td right>
                      {sold > 0 ? (
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${statusPill("sold")}`}>
                          {sold}
                        </span>
                      ) : <span className="text-stone-400">—</span>}
                    </Td>
                    <Td right className="font-medium tabular-nums">
                      {totalSold > 0 ? `$${totalSold.toLocaleString()}` : "—"}
                    </Td>
                  </tr>
                  {isOpen && (
                    <tr key={`det-${key}`} className="bg-stone-50/40">
                      <td colSpan="6" className="p-0">
                        <div className="overflow-x-auto">
                          <table className="min-w-full text-xs" data-testid={`auction-group-detail-${key}`}>
                            <thead className="text-left">
                              <tr>
                                <SubTh>{t("contract_number")}</SubTh>
                                <SubTh>{t("item")}</SubTh>
                                <SubTh right>{t("starting_price")}</SubTh>
                                <SubTh right>{t("sold_price")}</SubTh>
                                <SubTh>{t("buyer_name")}</SubTh>
                                <SubTh>{t("status")}</SubTh>
                                <SubTh right>{t("actions")}</SubTh>
                              </tr>
                            </thead>
                            <tbody>
                              {g.items.map((r) => (
                                <tr key={r.id} className="border-t border-stone-100">
                                  <SubTd className="font-medium whitespace-nowrap">{r.contract_number}</SubTd>
                                  <SubTd>
                                    <span className="inline-block text-[10px] uppercase tracking-wider text-stone-500 bg-stone-100 border border-stone-200 rounded px-1.5 py-0.5">
                                      {r.item_type}
                                    </span>
                                  </SubTd>
                                  <SubTd right>${Number(r.starting_price || 0).toLocaleString()}</SubTd>
                                  <SubTd right className="font-medium">
                                    {r.sold_price ? `$${Number(r.sold_price).toLocaleString()}` : "—"}
                                  </SubTd>
                                  <SubTd className="max-w-[180px] truncate" title={r.buyer_name || ""}>
                                    {r.buyer_name || "—"}
                                  </SubTd>
                                  <SubTd>
                                    <span className={`text-xs px-2 py-0.5 rounded-full border ${statusPill(r.status)}`}>
                                      {r.status}
                                    </span>
                                  </SubTd>
                                  <SubTd right>
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
                                        <button
                                          type="button"
                                          onClick={() => previewInvoice(r)}
                                          data-testid={`auction-invoice-${r.id}`}
                                          className="inline-flex items-center gap-1 px-2.5 h-7 rounded-md bg-[#DC2626] text-white text-xs font-medium hover:bg-[#B91C1C] transition-colors whitespace-nowrap"
                                          title={`${t("preview") || "Preview"}: ${r.invoice_number}`}
                                        >
                                          <Eye className="w-3 h-3" /> {shortInvoice(r.invoice_number) || t("invoice")}
                                        </button>
                                      )}
                                      {isAdmin && (
                                        <button
                                          type="button"
                                          onClick={() => deleteAuction(r)}
                                          data-testid={`auction-delete-${r.id}`}
                                          className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-white border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors"
                                          title="Delete auction (admin only)"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                      )}
                                    </div>
                                  </SubTd>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {groups.length === 0 && (
              <tr>
                <td colSpan="6" className="p-8 text-center text-stone-500">
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
            <DialogDescription className="sr-only">
              Record the auction sale price, tax, buyer name and optional interest fee split.
            </DialogDescription>
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

      <PdfPreviewDialog
        open={pdfPreview.open}
        onOpenChange={(o) => setPdfPreview((p) => ({ ...p, open: o }))}
        url={pdfPreview.url}
        title={pdfPreview.title}
        downloadName={pdfPreview.filename}
      />
    </div>
  );
}

function Th({ children, right, className = "" }) {
  return (
    <th
      className={`px-3 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${
        right ? "text-right" : ""
      } ${className}`}
    >
      {children}
    </th>
  );
}
function Td({ children, right, className = "", ...rest }) {
  return <td className={`px-3 py-3 ${right ? "text-right" : ""} ${className}`} {...rest}>{children}</td>;
}
function SubTh({ children, right }) {
  return (
    <th className={`px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${right ? "text-right" : ""}`}>
      {children}
    </th>
  );
}
function SubTd({ children, right, className = "", ...rest }) {
  return <td className={`px-3 py-2 whitespace-nowrap ${right ? "text-right" : ""} ${className}`} {...rest}>{children}</td>;
}
