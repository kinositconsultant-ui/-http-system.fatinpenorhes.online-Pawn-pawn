import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, API_BASE, pdfUrl } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogFooter,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Plus, Trash2, FileDown, Gavel, MessageCircle, RefreshCw, ScrollText, Eye, QrCode, Camera } from "lucide-react";
import { toast } from "sonner";
import PdfPreviewDialog from "../components/PdfPreviewDialog";

const blank = {
  client_id: "",
  item_type: "car",
  item_id: "",
  loan_amount: "",
  interest_rate: "10",
  contract_date: new Date().toISOString().slice(0, 10),
  due_date: "",
  notes: "",
};

const DEFAULT_RATE_FALLBACK = { car: 10, motorcycle: 10, electronic: 15, pezadu: 10 };

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];
function formatYearMonth(ym) {
  const [y, m] = (ym || "").split("-");
  const mi = Number(m) - 1;
  if (!y || mi < 0 || mi > 11) return ym;
  return `${MONTH_NAMES[mi]} ${y}`;
}

export default function Contracts() {
  const { t } = useLang();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") || "";
  const [rows, setRows] = useState([]);
  const [clients, setClients] = useState([]);
  const [itemsByKind, setItemsByKind] = useState({ car: [], motorcycle: [], electronic: [], pezadu: [] });
  const [defaults, setDefaults] = useState(DEFAULT_RATE_FALLBACK);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [pdfPreview, setPdfPreview] = useState({ open: false, url: "", title: "", filename: "" });

  const openContractPdf = (r) => {
    setPdfPreview({
      open: true,
      url: `${API_BASE}/contracts/${r.id}/pdf`,
      title: `${t("contract")} ${r.contract_number || ""}`,
      filename: `${r.contract_number || "contract"}.pdf`,
    });
  };

  const load = async () => {
    const [c, cl, cars, mc, el, pz, s] = await Promise.all([
      api.get("/contracts"),
      api.get("/clients"),
      api.get("/items/car"),
      api.get("/items/motorcycle"),
      api.get("/items/electronic"),
      api.get("/items/pezadu"),
      api.get("/settings"),
    ]);
    setRows(c.data);
    setClients(cl.data);
    setItemsByKind({ car: cars.data, motorcycle: mc.data, electronic: el.data, pezadu: pz.data });
    setDefaults({
      car: s.data.interest_rate_car ?? 10,
      motorcycle: s.data.interest_rate_motorcycle ?? 10,
      electronic: s.data.interest_rate_electronic ?? 15,
      pezadu: s.data.interest_rate_pezadu ?? 10,
    });
    // align default if dialog is closed (will be applied when opening)
  };

  useEffect(() => {
    load();
  }, []);

  const onChange = (k, v) =>
    setForm((f) => {
      const next = { ...f, [k]: v };
      if (k === "item_type") {
        next.item_id = "";
        next.interest_rate = String(defaults[v] ?? 10);
      }
      return next;
    });

  const submit = async () => {
    try {
      const payload = {
        ...form,
        loan_amount: Number(form.loan_amount),
        interest_rate: Number(form.interest_rate),
      };
      await api.post("/contracts", payload);
      toast.success("Contract created");
      setOpen(false);
      setForm(blank);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete contract and all payments?")) return;
    try {
      await api.delete(`/contracts/${id}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const moveToAuction = async (id) => {
    try {
      await api.post("/auctions/move", { contract_id: id, starting_price: 0 });
      toast.success("Moved to auction");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  // WhatsApp Preview & Send modal state
  const [waOpen, setWaOpen] = useState(false);
  const [waLoading, setWaLoading] = useState(false);
  const [waSending, setWaSending] = useState(false);
  const [waContract, setWaContract] = useState(null);
  const [waLanguage, setWaLanguage] = useState("en");
  const [waBody, setWaBody] = useState("");
  const [waPhone, setWaPhone] = useState("");
  const [waMeta, setWaMeta] = useState({});

  const loadPreview = async (contractId, language) => {
    setWaLoading(true);
    try {
      const { data } = await api.post("/whatsapp/preview", {
        contract_id: contractId,
        language,
      });
      setWaBody(data.body || "");
      setWaPhone(data.phone || "");
      setWaMeta({
        client_name: data.client_name,
        contract_number: data.contract_number,
        days: data.days,
        months: data.months,
        total_due: data.total_due,
        next_month_date: data.next_month_date,
      });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to build preview");
    } finally {
      setWaLoading(false);
    }
  };

  const sendWhatsApp = async (id, language) => {
    setWaContract(id);
    setWaLanguage(language);
    setWaOpen(true);
    await loadPreview(id, language);
  };

  const regeneratePreview = async () => {
    if (!waContract) return;
    await loadPreview(waContract, waLanguage);
  };

  const changeWaLanguage = async (lang) => {
    setWaLanguage(lang);
    if (waContract) await loadPreview(waContract, lang);
  };

  const submitWhatsApp = async () => {
    if (!waContract) return;
    if (!waBody.trim()) {
      toast.error("Message body is empty");
      return;
    }
    setWaSending(true);
    try {
      const { data } = await api.post("/whatsapp/adhoc-send", {
        contract_id: waContract,
        language: waLanguage,
        body: waBody,
        to_phone: waPhone || undefined,
      });
      toast.success(
        data.status === "mocked" ? t("whatsapp_mocked") : t("whatsapp_sent"),
      );
      setWaOpen(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally {
      setWaSending(false);
    }
  };

  const [reactOpen, setReactOpen] = useState(false);
  const [reactRow, setReactRow] = useState(null);
  const [reactDate, setReactDate] = useState("");

  const openReactivate = (row) => {
    setReactRow(row);
    // default new due date = today + 30 days
    const d = new Date();
    d.setDate(d.getDate() + 30);
    setReactDate(d.toISOString().slice(0, 10));
    setReactOpen(true);
  };
  const confirmReactivate = async () => {
    try {
      await api.post(`/contracts/${reactRow.id}/reactivate`, { new_due_date: reactDate });
      toast.success("Contract reactivated");
      setReactOpen(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const clientName = (id) => clients.find((c) => c.id === id)?.full_name || id;
  const itemLabel = (type, id) => {
    const it = itemsByKind[type]?.find((x) => x.id === id);
    if (!it) return id;
    return `${it.brand || ""} ${it.model || ""}`.trim();
  };
  const shortContract = (num) => {
    if (!num) return "—";
    const m = String(num).match(/^CTR-(\d{4})-0*(\d+)$/);
    return m ? `CT-${m[1]}-${m[2]}` : num;
  };

  const availableItems = itemsByKind[form.item_type]?.filter(
    (i) => i.status === "in_stock" || !i.status
  );

  // Pre-Auction list: contracts 1-10 days past due (status "grace_period"; legacy "overdue" alias)
  const preAuction = rows.filter(
    (r) =>
      (r.status === "grace_period" || r.status === "overdue") &&
      Number(r.days_overdue || 0) >= 1 &&
      Number(r.days_overdue || 0) <= 10
  );
  const auctionReady = rows.filter((r) => r.status === "auction_ready");

  // URL-driven status filter for the main contracts table. Cards on the
  // Dashboard link here with `?status=active|overdue|grace_period|redeemed|auction_ready`.
  // Legacy `?status=overdue` links are treated as `grace_period` (same 1-10 day window).
  const monthFilter = searchParams.get("month") || "";
  const filteredRows = useMemo(() => {
    let out = rows;
    if (statusFilter) {
      const sf = statusFilter === "overdue" ? "grace_period" : statusFilter;
      out = out.filter((r) => r.status === sf || (sf === "grace_period" && r.status === "overdue"));
    }
    if (monthFilter) out = out.filter((r) => (r.contract_date || "").startsWith(monthFilter));
    return out;
  }, [rows, statusFilter, monthFilter]);
  const clearStatusFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("status");
    setSearchParams(next, { replace: true });
  };
  const setMonthFilter = (val) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set("month", val);
    else next.delete("month");
    setSearchParams(next, { replace: true });
  };

  // Build the list of months present in the contracts dataset so the dropdown
  // only shows months that actually have contracts (avoids empty selections).
  const monthOptions = useMemo(() => {
    const set = new Set();
    for (const r of rows) {
      const ym = (r.contract_date || "").slice(0, 7);
      if (ym) set.add(ym);
    }
    return Array.from(set).sort((a, b) => b.localeCompare(a));
  }, [rows]);

  return (
    <div className="space-y-6" data-testid="contracts-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("contracts")}</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">{t("contracts")}</h1>
        </div>
        <div className="flex items-end gap-3 flex-wrap">
          <div className="space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-stone-500">
              {t("month")}
            </Label>
            <Select value={monthFilter || "all"} onValueChange={(v) => setMonthFilter(v === "all" ? "" : v)}>
              <SelectTrigger className="h-10 w-[180px]" data-testid="contracts-month-filter">
                <SelectValue placeholder={t("all_months") || "All months"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all" data-testid="contracts-month-option-all">{t("all_months") || "All months"}</SelectItem>
                {monthOptions.map((ym) => (
                  <SelectItem key={ym} value={ym} data-testid={`contracts-month-option-${ym}`}>
                    {formatYearMonth(ym)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="inline-flex items-center gap-1 rounded-md border border-stone-300 p-0.5 bg-white text-xs">
            <button
              type="button"
              onClick={() => {
                const params = new URLSearchParams();
                if (monthFilter) params.set("month", monthFilter);
                if (statusFilter) params.set("status", statusFilter);
                if (!monthFilter && !statusFilter && filteredRows.length) {
                  params.set("ids", filteredRows.map((r) => r.id).slice(0, 500).join(","));
                }
                const suffix = params.toString() ? `?${params.toString()}` : "";
                setPdfPreview({
                  open: true,
                  url: pdfUrl(`/contracts/labels-pdf${suffix}`),
                  title: `${t("print_labels") || "Print Labels"} · ${filteredRows.length} · single`,
                  filename: `fatin-penhores-labels-${monthFilter || statusFilter || "batch"}-single.pdf`,
                });
              }}
              data-testid="contracts-print-labels-btn"
              title={t("print_labels_hint") || "One sticker per page (A6 landscape)"}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[#1B2D5C] hover:bg-stone-100 font-medium"
            >
              <QrCode className="w-3.5 h-3.5" />
              {t("print_labels") || "Print Labels"}
            </button>
            <button
              type="button"
              onClick={() => {
                const params = new URLSearchParams();
                params.set("layout", "4up");
                if (monthFilter) params.set("month", monthFilter);
                if (statusFilter) params.set("status", statusFilter);
                if (!monthFilter && !statusFilter && filteredRows.length) {
                  params.set("ids", filteredRows.map((r) => r.id).slice(0, 500).join(","));
                }
                setPdfPreview({
                  open: true,
                  url: pdfUrl(`/contracts/labels-pdf?${params.toString()}`),
                  title: `${t("print_labels") || "Print Labels"} · ${filteredRows.length} · 4-up`,
                  filename: `fatin-penhores-labels-${monthFilter || statusFilter || "batch"}-4up.pdf`,
                });
              }}
              data-testid="contracts-print-labels-4up-btn"
              title={t("print_labels_4up_hint") || "4 labels per A4 sheet — standard printer paper"}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded text-stone-600 hover:bg-stone-100 border-l border-stone-200 font-medium"
            >
              4-up A4
            </button>
          </div>
          <Dialog
          open={open}
          onOpenChange={(o) => {
            setOpen(o);
            if (!o) setForm(blank);
          }}
        >
          <DialogTrigger asChild>
            <Button
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              data-testid="contract-new-btn"
            >
              <Plus className="w-4 h-4 mr-1" /> {t("new_contract")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{t("new_contract")}</DialogTitle>
              <DialogDescription className="sr-only">
                Create a new pawn contract linking a client and pawn item with loan amount, rate and due date.
              </DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label={t("client")}>
                <Select
                  value={form.client_id}
                  onValueChange={(v) => onChange("client_id", v)}
                >
                  <SelectTrigger data-testid="contract-client">
                    <SelectValue placeholder="—" />
                  </SelectTrigger>
                  <SelectContent>
                    {clients.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.full_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label={t("item")}>
                <div className="flex gap-2">
                  <Select
                    value={form.item_type}
                    onValueChange={(v) => onChange("item_type", v)}
                  >
                    <SelectTrigger className="w-40" data-testid="contract-item-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="car">{t("car")}</SelectItem>
                      <SelectItem value="motorcycle">{t("motorcycle")}</SelectItem>
                      <SelectItem value="electronic">{t("electronic")}</SelectItem>
                      <SelectItem value="pezadu">{t("pezadu")}</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={form.item_id}
                    onValueChange={(v) => onChange("item_id", v)}
                  >
                    <SelectTrigger className="flex-1" data-testid="contract-item-id">
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableItems?.map((i) => (
                        <SelectItem key={i.id} value={i.id}>
                          {`${i.brand || ""} ${i.model || ""}`.trim() || i.id.slice(0, 6)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </Field>
              <Field label={t("loan_amount")}>
                <Input
                  type="number"
                  step="0.01"
                  value={form.loan_amount}
                  onChange={(e) => onChange("loan_amount", e.target.value)}
                  data-testid="contract-loan-amount"
                />
              </Field>
              <Field label={t("interest_rate")}>
                <Select
                  value={form.interest_rate}
                  onValueChange={(v) => onChange("interest_rate", v)}
                >
                  <SelectTrigger data-testid="contract-interest-rate">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="10">10%</SelectItem>
                    <SelectItem value="15">15%</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label={t("contract_date")}>
                <Input
                  type="date"
                  value={form.contract_date}
                  onChange={(e) => onChange("contract_date", e.target.value)}
                  data-testid="contract-date"
                />
              </Field>
              <Field label={t("due_date")}>
                <Input
                  type="date"
                  value={form.due_date}
                  onChange={(e) => onChange("due_date", e.target.value)}
                  data-testid="contract-due-date"
                />
              </Field>
            </div>

            {/* Live Article-4 rule preview — computed from loan + rate so the
                cashier and client agree upfront on the maximum obligation. */}
            <RulePreviewCard
              loan={Number(form.loan_amount) || 0}
              rate={Number(form.interest_rate) || 0}
            />

            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {t("cancel")}
              </Button>
              <Button
                onClick={submit}
                className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
                data-testid="contract-save"
              >
                {t("save")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        </div>
      </header>

      {/* Pre-Auction / Auction Ready summary card */}
      {(preAuction.length > 0 || auctionReady.length > 0) && (
        <div className="rounded-lg border border-amber-200 bg-amber-50/60 shadow-sm overflow-hidden" data-testid="pre-auction-card">
          <div className="flex items-center justify-between px-5 py-3 border-b border-amber-200 bg-amber-100/60">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-md bg-amber-600 text-white flex items-center justify-center">
                <Gavel className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider font-semibold text-amber-800">{t("pre_auction") || "Pre-Auction"}</div>
                <div className="text-xs text-stone-600">
                  {t("pre_auction_hint") || "Contracts overdue 1-10 days. After 10 days they auto-move to Auction Ready."}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2 py-1 rounded bg-amber-200 text-amber-900 font-semibold">{preAuction.length} {t("pre_auction") || "Pre-Auction"}</span>
              <span className="px-2 py-1 rounded bg-red-200 text-red-900 font-semibold">{auctionReady.length} {t("auction_ready") || "Auction Ready"}</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="pre-auction-table">
              <thead className="text-left bg-amber-50/40">
                <tr>
                  <Th>{t("contract_number")}</Th>
                  <Th>{t("client")}</Th>
                  <Th>{t("item")}</Th>
                  <Th right>{t("days_overdue") || "Days Overdue"}</Th>
                  <Th right>{t("loan_amount")}</Th>
                  <Th right>{t("penalty")}</Th>
                  <Th>{t("status")}</Th>
                  <Th right>{t("actions")}</Th>
                </tr>
              </thead>
              <tbody>
                {[...preAuction, ...auctionReady]
                  .sort((a, b) => Number(b.days_overdue || 0) - Number(a.days_overdue || 0))
                  .map((r) => (
                    <tr key={r.id} className="border-t border-amber-100 hover:bg-amber-50/40" data-testid={`pre-auction-row-${r.id}`}>
                      <Td className="font-medium whitespace-nowrap">{shortContract(r.contract_number)}</Td>
                      <Td className="max-w-[160px] truncate">{clientName(r.client_id)}</Td>
                      <Td className="max-w-[180px] truncate">
                        <span className="inline-block text-[10px] uppercase tracking-wider text-stone-500 bg-stone-100 border border-stone-200 rounded px-1.5 py-0.5 mr-1.5">
                          {r.item_type}
                        </span>
                        {itemLabel(r.item_type, r.item_id)}
                      </Td>
                      <Td right>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${
                          Number(r.days_overdue || 0) > 10 ? "bg-red-100 text-red-800 border-red-300" :
                          Number(r.days_overdue || 0) >= 8 ? "bg-orange-100 text-orange-800 border-orange-300" :
                          Number(r.days_overdue || 0) >= 4 ? "bg-amber-100 text-amber-800 border-amber-300" :
                          "bg-yellow-100 text-yellow-800 border-yellow-300"
                        }`}>
                          {r.days_overdue || 0} {Number(r.days_overdue || 0) === 1 ? "day" : "days"}
                        </span>
                      </Td>
                      <Td right className="whitespace-nowrap">${Number(r.loan_amount).toLocaleString()}</Td>
                      <Td right className="whitespace-nowrap text-red-700 font-medium">
                        ${Number(r.penalty || 0).toLocaleString()}
                      </Td>
                      <Td><StatusBadge status={r.status} /></Td>
                      <Td right>
                        <div className="flex justify-end gap-0.5">
                          <button
                            onClick={() => sendWhatsApp(r.id, "tet")}
                            data-testid={`pa-whatsapp-${r.id}`}
                            className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                            title={t("send_whatsapp") || "Send WhatsApp reminder"}
                          >
                            <MessageCircle className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => openReactivate(r)}
                            data-testid={`pa-reactivate-${r.id}`}
                            className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                            title={t("reactivate") || "Reactivate (extend due date)"}
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                          </button>
                          {r.status === "auction_ready" && (
                            <button
                              onClick={() => {
                                if (window.confirm(`Move ${shortContract(r.contract_number)} to auction?`)) moveToAuction(r.id);
                              }}
                              data-testid={`pa-auction-${r.id}`}
                              className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#C17767] text-white hover:bg-[#A96253] transition-colors"
                              title={t("move_to_auction") || "Move to auction"}
                            >
                              <Gavel className="w-3.5 h-3.5" />
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => openContractPdf(r)}
                            data-testid={`pa-pdf-${r.id}`}
                            className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#DC2626] text-white hover:bg-[#B91C1C] transition-colors"
                            title={t("preview") || "Preview"}
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </Td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        {(statusFilter || monthFilter) && (
          <div
            className="px-4 py-2 border-b border-stone-200 bg-stone-50 flex items-center justify-between flex-wrap gap-2 text-sm"
            data-testid="contracts-filter-pill"
          >
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-stone-500">Filtered:</span>
              {statusFilter && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-stone-300 text-xs font-medium uppercase tracking-wider">
                  status · {statusFilter.replace(/_/g, " ")}
                </span>
              )}
              {monthFilter && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-stone-300 text-xs font-medium">
                  {formatYearMonth(monthFilter)}
                </span>
              )}
              <span className="text-xs text-stone-500">· {filteredRows.length} of {rows.length}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                const next = new URLSearchParams();
                setSearchParams(next, { replace: true });
              }}
              className="text-xs text-[#1B2D5C] hover:underline font-medium"
              data-testid="contracts-filter-clear"
            >
              Clear filter ×
            </button>
          </div>
        )}
        <table className="min-w-full text-[13px]" data-testid="contracts-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>{t("contract_number")}</Th>
              <Th>{t("client")}</Th>
              <Th>{t("item")}</Th>
              <Th right>{t("loan_amount")}</Th>
              <Th>{t("contract_date")} → {t("due_date")}</Th>
              <Th right>{t("remaining_balance")}</Th>
              <Th>{t("status")}</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((r) => {
              const highlighted = searchParams.get("highlight") === r.contract_number;
              return (
              <tr
                key={r.id}
                ref={highlighted ? (el) => el?.scrollIntoView({ block: "center" }) : undefined}
                className={`border-t border-stone-100 hover:bg-stone-50/50 ${highlighted ? "bg-amber-50 ring-2 ring-amber-300" : ""}`}
                data-testid={highlighted ? `contract-highlight-${r.id}` : undefined}
              >
                <Td className="font-medium whitespace-nowrap" title={r.contract_number}>{shortContract(r.contract_number)}</Td>
                <Td className="max-w-[140px] truncate" title={clientName(r.client_id)}>{clientName(r.client_id)}</Td>
                <Td className="whitespace-nowrap">
                  <span className="inline-block text-[10px] uppercase tracking-wider text-stone-500 bg-stone-100 border border-stone-200 rounded px-1.5 py-0.5 mr-1.5">
                    {r.item_type}
                  </span>
                  <span className="align-middle text-xs" title={itemLabel(r.item_type, r.item_id)}>
                    {itemLabel(r.item_type, r.item_id)}
                  </span>
                  {r.has_item_photo === false && (
                    <Link
                      to="/items"
                      title="No photo on file — click to add one. Photo prints on the QR label."
                      data-testid={`contract-nophoto-${r.id}`}
                      className="ml-1.5 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800 hover:bg-amber-100"
                    >
                      <Camera className="w-3 h-3" />
                      no photo
                    </Link>
                  )}
                </Td>
                <Td right className="whitespace-nowrap">
                  {r.original_loan_amount && Math.abs(Number(r.original_loan_amount) - Number(r.principal_remaining ?? r.loan_amount)) > 0.01 ? (
                    <>
                      <div className="text-xs text-stone-400 line-through">
                        ${Number(r.original_loan_amount).toLocaleString()}
                      </div>
                      <div className="font-medium text-[#1B2D5C]">
                        ${Number(r.principal_remaining ?? r.loan_amount).toLocaleString()}
                      </div>
                      {(() => {
                        const orig = Number(r.original_loan_amount);
                        const rem = Number(r.principal_remaining ?? r.loan_amount);
                        const paid = orig - rem;
                        const pct = Math.min(100, Math.round((paid / orig) * 100));
                        return (
                          <div
                            className="mt-1 flex flex-col items-end gap-0.5"
                            data-testid={`contract-progress-${r.id}`}
                            title={`Principal paid: $${paid.toLocaleString()} / $${orig.toLocaleString()}`}
                          >
                            <div className="w-24 h-1 rounded-full bg-stone-200 overflow-hidden">
                              <div
                                className="h-full bg-emerald-600"
                                style={{ width: `${pct}%` }}
                              ></div>
                            </div>
                            <div className="text-[9px] text-emerald-700 font-medium">
                              {pct}% paid off
                            </div>
                          </div>
                        );
                      })()}
                    </>
                  ) : (
                    <div>${Number(r.loan_amount).toLocaleString()}</div>
                  )}
                  <div className="text-xs text-stone-500">@ {r.interest_rate}%</div>
                </Td>
                <Td className="whitespace-nowrap text-xs">
                  <div>{r.contract_date}</div>
                  <div className="text-stone-500">→ {r.due_date}</div>
                </Td>
                <Td right className="whitespace-nowrap">
                  <div className="font-medium">${Number(r.remaining_balance ?? 0).toLocaleString()}</div>
                  {Number(r.penalty || 0) > 0 && (
                    <div className="text-[10px] text-[#993333] font-medium">
                      +${Number(r.penalty).toLocaleString()} {t("penalty").toLowerCase()}
                    </div>
                  )}
                </Td>
                <Td className="whitespace-nowrap">
                  <StatusBadge status={r.status} />
                </Td>
                <Td right>
                  <div className="flex justify-end gap-0.5">
                    <button
                      type="button"
                      onClick={() => openContractPdf(r)}
                      data-testid={`contract-pdf-${r.id}`}
                      className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#DC2626] text-white hover:bg-[#B91C1C] transition-colors"
                      title={`${t("preview") || "Preview"} — Nov-2026 math`}
                    >
                      <Eye className="w-3 h-3" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setPdfPreview({
                        open: true,
                        url: pdfUrl(`/contracts/${r.id}/label-pdf`),
                        title: `${t("qr_label") || "QR Label"} · ${r.contract_number}`,
                        filename: `${r.contract_number}-label.pdf`,
                      })}
                      data-testid={`contract-label-${r.id}`}
                      title={t("qr_label_hint") || "Printable QR sticker for the physical item"}
                      className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#1B2D5C] text-white hover:bg-[#0F1B3A] transition-colors"
                    >
                      <QrCode className="w-3 h-3" />
                    </button>
                    {(r.status === "overdue" || r.status === "grace_period") && (
                      <button
                        onClick={() => openReactivate(r)}
                        data-testid={`contract-reactivate-${r.id}`}
                        className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#4C7F62] text-white hover:bg-[#3F6B52] transition-colors"
                        title={t("reactivate")}
                      >
                        <RefreshCw className="w-3 h-3" />
                      </button>
                    )}
                    {["active", "overdue", "grace_period"].includes(r.status) && (
                      <button
                        onClick={() => moveToAuction(r.id)}
                        data-testid={`contract-auction-${r.id}`}
                        className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#C17767] text-white hover:bg-[#A96253] transition-colors"
                        title={t("move_to_auction")}
                      >
                        <Gavel className="w-3 h-3" />
                      </button>
                    )}
                    {["active", "overdue", "grace_period"].includes(r.status) && (
                      <button
                        onClick={() => sendWhatsApp(r.id, "en")}
                        data-testid={`contract-whatsapp-${r.id}`}
                        className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#25D366] text-white hover:bg-[#1EA952] transition-colors"
                        title={t("send_whatsapp")}
                      >
                        <MessageCircle className="w-3 h-3" />
                      </button>
                    )}
                    <button
                      onClick={() => remove(r.id)}
                      data-testid={`contract-delete-${r.id}`}
                      className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#993333] text-white hover:bg-[#7A2828] transition-colors"
                      title={t("delete")}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </Td>
              </tr>
              );
            })}
            {filteredRows.length === 0 && (
              <tr>
                <td colSpan="8" className="p-8 text-center text-stone-500">
                  {statusFilter ? `No contracts with status "${statusFilter}"` : "No contracts"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* WhatsApp Preview & Send dialog */}
      <Dialog open={waOpen} onOpenChange={setWaOpen}>
        <DialogContent className="max-w-lg" data-testid="wa-preview-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-800">
              <MessageCircle className="w-5 h-5" />
              {t("whatsapp_preview_title")}
            </DialogTitle>
            <DialogDescription>
              {t("whatsapp_preview_desc")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {waMeta.contract_number && (
              <div className="rounded-md border border-emerald-100 bg-emerald-50/60 px-3 py-2 text-xs text-stone-700 grid grid-cols-2 gap-y-1">
                <div><span className="text-stone-500">Contract:</span> <span className="font-medium">{waMeta.contract_number}</span></div>
                <div><span className="text-stone-500">Client:</span> <span className="font-medium">{waMeta.client_name || "—"}</span></div>
                <div><span className="text-stone-500">Days overdue:</span> <span className="font-medium">{waMeta.days ?? "—"}</span></div>
                <div><span className="text-stone-500">Total due:</span> <span className="font-medium">${Number(waMeta.total_due || 0).toLocaleString()}</span></div>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-[1fr,140px] gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-stone-500">{t("whatsapp_to")}</Label>
                <Input
                  value={waPhone}
                  onChange={(e) => setWaPhone(e.target.value)}
                  placeholder="+670..."
                  data-testid="wa-to-phone"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-stone-500">{t("whatsapp_language")}</Label>
                <Select value={waLanguage} onValueChange={changeWaLanguage}>
                  <SelectTrigger data-testid="wa-lang"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="tet">Tetum</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs uppercase tracking-wider text-stone-500">{t("whatsapp_message")}</Label>
                <button
                  type="button"
                  onClick={regeneratePreview}
                  className="text-xs text-emerald-700 hover:underline inline-flex items-center gap-1 disabled:opacity-50"
                  disabled={waLoading || !waContract}
                  data-testid="wa-regenerate"
                >
                  <RefreshCw className="w-3 h-3" /> {t("whatsapp_regenerate")}
                </button>
              </div>
              <Textarea
                value={waBody}
                onChange={(e) => setWaBody(e.target.value)}
                rows={8}
                className="font-mono text-xs"
                data-testid="wa-body"
                disabled={waLoading}
              />
              <div className="text-xs text-stone-500 text-right">{waBody.length} chars</div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWaOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              onClick={submitWhatsApp}
              disabled={waLoading || waSending || !waBody.trim() || !waPhone.trim()}
              className="bg-emerald-700 hover:bg-emerald-800"
              data-testid="wa-send"
            >
              {waSending ? "…" : t("whatsapp_send")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reactivate dialog */}
      <Dialog open={reactOpen} onOpenChange={setReactOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("reactivate_contract")}</DialogTitle>
            <DialogDescription className="sr-only">
              Extend the contract due date up to the 62-day maximum from the original start date.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-stone-600">
              {reactRow?.contract_number} — extending due date. Total contract length still capped at 2 months from the original start date.
            </p>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">
                {t("new_due_date")}
              </Label>
              <Input
                type="date"
                value={reactDate}
                onChange={(e) => setReactDate(e.target.value)}
                data-testid="reactivate-due-date"
              />
            </div>
            {/* Live obligation preview based on the current principal + rate
                so cashiers can quote the exact "penalty if late" number as
                they confirm the amendment. */}
            <RulePreviewCard
              loan={Number(reactRow?.principal_remaining ?? reactRow?.loan_amount ?? 0)}
              rate={Number(reactRow?.interest_rate ?? 0)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReactOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              onClick={confirmReactivate}
              className="bg-[#4C7F62] hover:bg-[#3F6B52]"
              data-testid="reactivate-confirm"
            >
              {t("reactivate")}
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

function StatusBadge({ status }) {
  const map = {
    active: "bg-emerald-50 text-emerald-800 border-emerald-200",
    overdue: "bg-amber-50 text-amber-800 border-amber-200",
    grace_period: "bg-amber-50 text-amber-800 border-amber-200",
    auction_ready: "bg-red-50 text-red-800 border-red-200",
    redeemed: "bg-stone-100 text-stone-700 border-stone-200",
    auction: "bg-orange-50 text-orange-800 border-orange-200",
    sold: "bg-purple-50 text-purple-800 border-purple-200",
  };
  const labelMap = {
    grace_period: "grace period",
    auction_ready: "auction ready",
  };
  const label = labelMap[status] || status;
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full border ${
        map[status] || "bg-stone-100 text-stone-700 border-stone-200"
      }`}
    >
      {label}
    </span>
  );
}

function Field({ label, children }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-wider text-stone-500">{label}</Label>
      {children}
    </div>
  );
}

function Th({ children, right }) {
  return (
    <th
      className={`px-2 py-2.5 text-[10px] uppercase tracking-wider text-stone-500 font-semibold leading-tight ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}

function Td({ children, right, className = "" }) {
  return (
    <td className={`px-2 py-2 ${right ? "text-right" : ""} ${className}`}>
      {children}
    </td>
  );
}

/**
 * Live preview of Article 2 + Article 4 + Article 8 maximum obligation so
 * the cashier can walk the client through the numbers before signing. The
 * shown values match what the backend caps at (2 months of interest max +
 * one-time 10% penalty).
 */
function RulePreviewCard({ loan, rate }) {
  if (!loan || !rate) {
    return (
      <div
        className="mt-1 mb-2 p-3 rounded-md border border-dashed border-stone-300 bg-stone-50 text-xs text-stone-500"
        data-testid="rule-preview-empty"
      >
        Fill in loan amount and interest rate to see the Article 4 maximum obligation.
      </div>
    );
  }
  const monthly = loan * rate / 100;
  const twoMonthInterest = 2 * monthly;
  // Penalty (Article 8) matches the contract's interest rate — cashiers can
  // quote it live to the client so there are no surprises when it kicks in.
  const penalty = loan * rate / 100;
  const maxDue = loan + twoMonthInterest + penalty;
  const money = (n) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return (
    <div
      className="mt-1 mb-2 p-3 rounded-md border border-[#1B2D5C]/20 bg-[#1B2D5C]/[0.04]"
      data-testid="rule-preview"
    >
      <div className="text-[11px] uppercase tracking-wider font-semibold text-[#1B2D5C] mb-2">
        Article 4 — Maximum obligation preview
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <RuleRow label="Monthly interest" value={money(monthly)} sub={`${rate}% × principal`} />
        <RuleRow label="Interest × 2 max" value={money(twoMonthInterest)} sub="Article 4 cap" />
        <RuleRow
          label="Penalty if late"
          value={money(penalty)}
          sub={`${rate}% × principal (Art. 8)`}
          data-testid="rule-preview-penalty"
        />
        <RuleRow
          label="Total Selu max"
          value={money(maxDue)}
          sub="principal + 2×int + penalty"
          highlight
        />
      </div>
    </div>
  );
}
function RuleRow({ label, value, sub, highlight = false }) {
  return (
    <div className={`p-2 rounded ${highlight ? "bg-white border border-[#1B2D5C]" : "bg-white/60"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`font-display text-base leading-tight ${highlight ? "text-[#1B2D5C] font-semibold" : "text-stone-900"}`}>
        {value}
      </div>
      {sub && <div className="text-[10px] text-stone-500 mt-0.5">{sub}</div>}
    </div>
  );
}

