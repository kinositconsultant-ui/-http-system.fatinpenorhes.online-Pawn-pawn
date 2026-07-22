import { useEffect, useMemo, useState, Fragment } from "react";
import { useSearchParams } from "react-router-dom";
import { api, API_BASE } from "../lib/api";
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
  DialogTrigger,
  DialogFooter,
} from "../components/ui/dialog";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Plus, FileDown, AlertTriangle, Coins, Banknote, Trash2, ChevronDown, ChevronRight, Eye, ScrollText } from "lucide-react";
import { toast } from "sonner";
import { shortContract, shortReceipt } from "../lib/docNumbers";
import PdfPreviewDialog from "../components/PdfPreviewDialog";

const blank = {
  contract_id: "",
  amount: "",
  type: "partial",
  date: new Date().toISOString().slice(0, 10),
  notes: "",
};

export default function Payments() {
  const { t } = useLang();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [searchParams, setSearchParams] = useSearchParams();
  const contractFilter = searchParams.get("contract") || "";
  const [rows, setRows] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [clients, setClients] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  // Free-text search in the New Payment dialog. Matches contract_number,
  // client name, or item_type — cashiers can type "535" or "Maria" or the
  // last four digits of a plate to find the row fast.
  const [searchQuery, setSearchQuery] = useState("");
  const [pdfPreview, setPdfPreview] = useState({ open: false, url: "", title: "", filename: "" });

  const openPaymentPdf = (r) => {
    // Handle both single-payment receipts and the new contract-level
    // payment-history summary. The history button passes `_url` and `_title`
    // so we don't need a separate handler.
    if (r._url) {
      setPdfPreview({
        open: true,
        url: r._url,
        title: r._title || "Payment History",
        filename: `${r.receipt_number || "payment-history"}.pdf`,
      });
      return;
    }
    setPdfPreview({
      open: true,
      url: `${API_BASE}/payments/${r.id}/pdf`,
      title: `${t("payment_receipt") || "Receipt"} ${shortReceipt(r.receipt_number) || r.receipt_number}`,
      filename: `${r.receipt_number || "receipt"}.pdf`,
    });
  };

  // Overdue dialog state
  const [odOpen, setOdOpen] = useState(false);
  const [odContractId, setOdContractId] = useState("");
  const [odMode, setOdMode] = useState("overdue_full");
  const [odDate, setOdDate] = useState(new Date().toISOString().slice(0, 10));

  const load = async () => {
    const [p, c, cl] = await Promise.all([
      api.get("/payments"),
      api.get("/contracts"),
      api.get("/clients"),
    ]);
    setRows(p.data);
    setContracts(c.data);
    setClients(cl.data);
  };
  useEffect(() => {
    load();
  }, []);

  const deletePayment = async (payment) => {
    const label = payment.receipt_number || payment.id;
    if (!window.confirm(`Delete payment ${label}?\nThis will recompute the contract balance. This action is logged.`)) return;
    try {
      await api.delete(`/payments/${payment.id}`);
      toast.success("Payment deleted");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const onChange = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    try {
      await api.post("/payments", { ...form, amount: Number(form.amount) });
      toast.success("Payment recorded");
      setOpen(false);
      setForm(blank);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const contractLabel = (id) => {
    const c = contracts.find((x) => x.id === id);
    return c ? shortContract(c.contract_number) : id;
  };
  const contractById = (id) => contracts.find((x) => x.id === id) || null;
  const clientById = (id) => clients.find((x) => x.id === id) || null;
  const clientNameById = (id) => clientById(id)?.full_name || "";
  const selectedContract = contracts.find((c) => c.id === form.contract_id);
  const selectedClient = selectedContract ? clientById(selectedContract.client_id) : null;
  // Filter open contracts by the search query so cashiers can quickly find
  // the row by contract number, client name, or item type.
  const payableContracts = useMemo(
    () => contracts.filter((c) => ["active", "overdue", "grace_period", "auction_ready"].includes(c.status)),
    [contracts],
  );
  const matchedContracts = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return payableContracts.slice(0, 8);
    return payableContracts.filter((c) => {
      const name = (clientById(c.client_id)?.full_name || "").toLowerCase();
      return (
        (c.contract_number || "").toLowerCase().includes(q) ||
        name.includes(q) ||
        (c.item_type || "").toLowerCase().includes(q)
      );
    }).slice(0, 20);
  }, [searchQuery, payableContracts, clients]);
  const overdueContracts = useMemo(
    () => contracts.filter((c) => c.status === "overdue" || c.status === "grace_period" || c.status === "auction_ready"),
    [contracts]
  );
  const odContract = contracts.find((c) => c.id === odContractId);

  const odAmount = useMemo(() => {
    if (!odContract) return 0;
    const interest = Number(odContract.interest_remaining || 0);
    const penalty = Number(odContract.penalty || 0);
    const principal = Number(odContract.principal_remaining || 0);
    if (odMode === "overdue_full") return principal + interest + penalty;
    if (odMode === "overdue_interest_pen") return interest + penalty;
    if (odMode === "overdue_penalty_only") return penalty;
    return 0;
  }, [odContract, odMode]);

  const submitOverdue = async () => {
    if (!odContractId) {
      toast.error("Select a contract");
      return;
    }
    if (odAmount <= 0) {
      toast.error("Nothing to collect");
      return;
    }
    try {
      await api.post("/payments", {
        contract_id: odContractId,
        amount: Number(odAmount.toFixed(2)),
        type: odMode,
        date: odDate,
        notes: `Overdue payment: ${odMode}`,
      });
      toast.success("Overdue payment recorded");
      setOdOpen(false);
      setOdContractId("");
      setOdMode("overdue_full");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  // URL-driven filter — if ?contract=CTR-... is present, only show payments
  // on that contract across all 3 tabs. Cashiers deep-link here from the
  // Contracts page → "History" button.
  const filteredForContract = useMemo(() => {
    if (!contractFilter) return rows;
    return rows.filter((r) => {
      const c = contracts.find((x) => x.id === r.contract_id);
      return c?.contract_number === contractFilter;
    });
  }, [rows, contracts, contractFilter]);

  const overduePayments = filteredForContract.filter((r) =>
    ["overdue_full", "overdue_interest_pen", "overdue_penalty_only"].includes(r.type)
  );
  const regularPayments = filteredForContract.filter(
    (r) => !["overdue_full", "overdue_interest_pen", "overdue_penalty_only", "disbursement"].includes(r.type)
  );
  const disbursements = filteredForContract.filter((r) => r.type === "disbursement");

  return (
    <div className="space-y-6" data-testid="payments-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("payments")}</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">{t("payments")}</h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="border-amber-300 text-amber-800 hover:bg-amber-50"
            onClick={() => setOdOpen(true)}
            data-testid="overdue-payment-btn"
          >
            <AlertTriangle className="w-4 h-4 mr-1" /> {t("overdue_payment")}
          </Button>
          <Dialog
            open={open}
            onOpenChange={(o) => {
              setOpen(o);
              if (!o) {
                setForm(blank);
                setSearchQuery("");
              }
            }}
          >
            <DialogTrigger asChild>
              <Button
                className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
                data-testid="payment-new-btn"
              >
                <Plus className="w-4 h-4 mr-1" /> {t("new_payment")}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>{t("new_payment")}</DialogTitle>
                <DialogDescription className="sr-only">
                  Record a new client payment against an active or overdue contract.
                </DialogDescription>
              </DialogHeader>
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
                {/* LEFT — search + contract detail */}
                <div className="lg:col-span-3 space-y-3" data-testid="np-contract-panel">
                  <div>
                    <div className="text-eyebrow mb-1.5">
                      {t("search_contract") || "Search contract"}
                    </div>
                    <Input
                      autoFocus
                      type="text"
                      placeholder={t("search_contract_ph") || "Type contract number, client name, or item type…"}
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        // Typing again clears the selection so the list re-opens
                        if (form.contract_id) onChange("contract_id", "");
                      }}
                      data-testid="np-search"
                    />
                  </div>
                  {!form.contract_id && (
                    <div
                      className="max-h-60 overflow-auto rounded-md border border-stone-200 bg-white divide-y divide-stone-100"
                      data-testid="np-search-results"
                    >
                      {matchedContracts.length === 0 ? (
                        <div className="p-3 text-sm text-stone-500">
                          {t("no_matches") || "No matching contracts"}
                        </div>
                      ) : (
                        matchedContracts.map((c) => (
                          <button
                            key={c.id}
                            type="button"
                            onClick={() => {
                              onChange("contract_id", c.id);
                              setSearchQuery(c.contract_number || "");
                            }}
                            data-testid={`np-pick-${c.id}`}
                            className="w-full text-left px-3 py-2 hover:bg-stone-50 flex items-center justify-between gap-3 text-sm"
                          >
                            <div className="min-w-0">
                              <div className="font-medium">{c.contract_number}</div>
                              <div className="text-xs text-stone-500 truncate">
                                {clientNameById(c.client_id) || "—"} · {c.item_type}
                              </div>
                            </div>
                            <div className="text-xs text-stone-600 whitespace-nowrap">
                              ${Number(c.remaining_balance || 0).toLocaleString()} left
                              <span className="ml-1 text-[10px] uppercase tracking-wider text-stone-400">
                                {c.status === "grace_period" ? "grace" : c.status}
                              </span>
                            </div>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                  {selectedContract && (
                    <div
                      className="p-3 rounded-md border border-[#1B2D5C]/20 bg-[#1B2D5C]/[0.04] space-y-2"
                      data-testid="np-contract-preview"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-display text-lg text-[#1B2D5C]">
                            {selectedContract.contract_number}
                          </div>
                          <div className="text-xs text-stone-600">
                            {selectedClient?.full_name || "—"}
                            {selectedClient?.phone ? ` · ${selectedClient.phone}` : ""}
                          </div>
                        </div>
                        <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                          selectedContract.status === "auction_ready"
                            ? "bg-red-50 text-red-800 border-red-200"
                            : selectedContract.status === "grace_period" || selectedContract.status === "overdue"
                            ? "bg-amber-50 text-amber-800 border-amber-200"
                            : "bg-emerald-50 text-emerald-800 border-emerald-200"
                        }`}>
                          {selectedContract.status === "grace_period" ? "grace period" : selectedContract.status}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-stone-500">{t("interest_left")}</div>
                          <div className="font-display text-base text-amber-700" data-testid="np-interest-remaining">
                            ${Number(selectedContract.interest_remaining || 0).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-stone-500">{t("total_due")}</div>
                          <div className="font-display text-base" data-testid="np-total-due">
                            ${Number(selectedContract.total_due || 0).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-stone-500">{t("paid_amount")}</div>
                          <div className="font-display text-base" data-testid="np-paid">
                            ${Number(selectedContract.paid_amount || 0).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-wider text-stone-500">{t("remaining_balance")}</div>
                          <div className="font-display text-base text-[#C17767]" data-testid="np-remaining">
                            ${Number(selectedContract.remaining_balance || 0).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-stone-600 pt-1 border-t border-stone-200">
                        <div><span className="text-stone-400">Item:</span> {selectedContract.item_type}</div>
                        <div><span className="text-stone-400">Rate:</span> {selectedContract.interest_rate}%</div>
                        <div><span className="text-stone-400">Days overdue:</span> {selectedContract.days_overdue || 0}</div>
                        <div><span className="text-stone-400">Due:</span> {selectedContract.due_date || "—"}</div>
                        <div><span className="text-stone-400">Loan:</span> ${Number(selectedContract.loan_amount || 0).toLocaleString()}</div>
                        <div><span className="text-stone-400">Principal left:</span> ${Number(selectedContract.principal_remaining || 0).toLocaleString()}</div>
                      </div>
                    </div>
                  )}
                </div>

                {/* RIGHT — payment form */}
                <div className="lg:col-span-2 space-y-3" data-testid="np-form-panel">
                  <Field label={t("payment_type")}>
                    <Select value={form.type} onValueChange={(v) => onChange("type", v)}>
                      <SelectTrigger data-testid="payment-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="full">{t("full")}</SelectItem>
                        <SelectItem value="partial">{t("partial")}</SelectItem>
                        <SelectItem value="interest_only">{t("interest_only")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label={t("amount")}>
                    <Input
                      type="number"
                      step="0.01"
                      value={form.amount}
                      onChange={(e) => onChange("amount", e.target.value)}
                      data-testid="payment-amount"
                    />
                  </Field>
                  <Field label={t("date")}>
                    <Input
                      type="date"
                      value={form.date}
                      onChange={(e) => onChange("date", e.target.value)}
                      data-testid="payment-date"
                    />
                  </Field>
                  {selectedContract && form.type === "full" && (
                    <button
                      type="button"
                      onClick={() => onChange("amount", String(selectedContract.remaining_balance || 0))}
                      className="text-xs text-[#1B2D5C] hover:underline"
                      data-testid="np-fill-full"
                    >
                      {t("fill_remaining") || "Fill remaining"}: ${Number(selectedContract.remaining_balance || 0).toLocaleString()}
                    </button>
                  )}
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>
                  {t("cancel")}
                </Button>
                <Button
                  onClick={submit}
                  className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
                  data-testid="payment-save"
                  disabled={!form.contract_id || !form.amount}
                >
                  {t("save")}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      {contractFilter && (
        <div
          className="px-4 py-2 rounded-md bg-[#1B2D5C]/[0.06] border border-[#1B2D5C]/20 flex items-center justify-between flex-wrap gap-2 text-sm"
          data-testid="payments-filter-pill"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-stone-500">Filtered by contract:</span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-stone-300 text-xs font-medium">
              {contractFilter}
            </span>
            <span className="text-xs text-stone-500">· {filteredForContract.length} of {rows.length} payments</span>
          </div>
          <button
            type="button"
            onClick={() => {
              const next = new URLSearchParams(searchParams);
              next.delete("contract");
              setSearchParams(next, { replace: true });
            }}
            className="text-xs text-[#1B2D5C] hover:underline font-medium"
            data-testid="payments-filter-clear"
          >
            Clear filter ×
          </button>
        </div>
      )}

      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all" data-testid="tab-all-payments">
            {t("payments")} <span className="ml-1 text-xs text-stone-500">({regularPayments.length})</span>
          </TabsTrigger>
          <TabsTrigger value="overdue" data-testid="tab-overdue-payments">
            <AlertTriangle className="w-3.5 h-3.5 mr-1 text-amber-700" />
            {t("overdue_payment")} <span className="ml-1 text-xs text-stone-500">({overduePayments.length})</span>
          </TabsTrigger>
          <TabsTrigger value="disbursements" data-testid="tab-disbursements">
            <Banknote className="w-3.5 h-3.5 mr-1 text-emerald-700" />
            {t("disbursements")} <span className="ml-1 text-xs text-stone-500">({disbursements.length})</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="all">
          <PaymentsTable rows={regularPayments} contractLabel={contractLabel} contractById={contractById} t={t} testid="payments-table" isAdmin={isAdmin} onDelete={deletePayment} onPreview={openPaymentPdf} />
        </TabsContent>
        <TabsContent value="overdue">
          <PaymentsTable rows={overduePayments} contractLabel={contractLabel} contractById={contractById} t={t} testid="overdue-payments-table" overdue isAdmin={isAdmin} onDelete={deletePayment} onPreview={openPaymentPdf} />
        </TabsContent>
        <TabsContent value="disbursements">
          <PaymentsTable rows={disbursements} contractLabel={contractLabel} contractById={contractById} t={t} testid="disbursements-table" disbursement isAdmin={isAdmin} onDelete={deletePayment} onPreview={openPaymentPdf} />
        </TabsContent>
      </Tabs>

      {/* Overdue Payment dialog */}
      <Dialog open={odOpen} onOpenChange={setOdOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-700" />
              {t("overdue_payment")}
            </DialogTitle>
            <DialogDescription className="sr-only">
              Record an overdue-contract payment covering penalty, interest and/or principal.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-stone-500">{t("contract_number")}</Label>
              <Select value={odContractId} onValueChange={setOdContractId}>
                <SelectTrigger data-testid="overdue-contract">
                  <SelectValue placeholder="Select overdue contract" />
                </SelectTrigger>
                <SelectContent>
                  {overdueContracts.length === 0 && (
                    <div className="px-3 py-2 text-sm text-stone-500">No overdue contracts</div>
                  )}
                  {overdueContracts.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.contract_number} · {c.days_overdue}d overdue · ${Number(c.remaining_balance || 0).toLocaleString()} due
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {odContract && (
              <div className="grid grid-cols-3 gap-3 text-sm bg-amber-50/60 border border-amber-200 rounded-md p-3">
                <div>
                  <div className="text-eyebrow">{t("principal_left")}</div>
                  <div className="font-display text-base">${Number(odContract.principal_remaining || 0).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-eyebrow">{t("interest_left")}</div>
                  <div className="font-display text-base">${Number(odContract.interest_remaining || 0).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-eyebrow">{t("penalty")}</div>
                  <div className="font-display text-base text-red-700">${Number(odContract.penalty || 0).toLocaleString()}</div>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label className="text-xs uppercase tracking-wider text-stone-500">{t("payment_type")}</Label>
              <div className="grid grid-cols-1 gap-2">
                <ModeChoice
                  active={odMode === "overdue_full"}
                  onClick={() => setOdMode("overdue_full")}
                  icon={<Banknote className="w-4 h-4" />}
                  title={t("pay_full")}
                  hint="Close out the contract: principal + interest + penalty."
                  testid="mode-full"
                />
                <ModeChoice
                  active={odMode === "overdue_interest_pen"}
                  onClick={() => setOdMode("overdue_interest_pen")}
                  icon={<Coins className="w-4 h-4" />}
                  title={t("pay_interest_penalty")}
                  hint="Pay interest + penalty (principal stays open)."
                  testid="mode-interest-penalty"
                />
                <ModeChoice
                  active={odMode === "overdue_penalty_only"}
                  onClick={() => setOdMode("overdue_penalty_only")}
                  icon={<AlertTriangle className="w-4 h-4" />}
                  title={t("pay_penalty_only")}
                  hint="Collect only the 10% penalty for the records."
                  testid="mode-penalty"
                />
              </div>
            </div>

            <div className="flex items-end justify-between gap-3 bg-stone-50 border border-stone-200 rounded-md p-3 flex-wrap">
              <div>
                <div className="text-eyebrow">{t("amount_to_collect")}</div>
                <div className="font-display text-2xl text-[#1B2D5C]" data-testid="overdue-amount">
                  ${Number(odAmount || 0).toLocaleString()}
                </div>
              </div>
              <div className="w-40">
                <Label className="text-xs uppercase tracking-wider text-stone-500">{t("date")}</Label>
                <Input
                  type="date"
                  value={odDate}
                  onChange={(e) => setOdDate(e.target.value)}
                  data-testid="overdue-date"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOdOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              onClick={submitOverdue}
              className="bg-amber-700 hover:bg-amber-800"
              data-testid="overdue-save"
              disabled={!odContractId || odAmount <= 0}
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

function PaymentsTable({ rows, contractLabel, contractById, t, testid, overdue = false, disbursement = false, isAdmin = false, onDelete, onPreview }) {
  const [expanded, setExpanded] = useState({});
  const typeBadge = (type) => {
    const map = {
      full: "bg-emerald-50 text-emerald-800 border-emerald-200",
      interest_only: "bg-amber-50 text-amber-800 border-amber-200",
      partial: "bg-stone-100 text-stone-700 border-stone-200",
      overdue_full: "bg-emerald-100 text-emerald-900 border-emerald-300",
      overdue_interest_pen: "bg-amber-100 text-amber-900 border-amber-300",
      overdue_penalty_only: "bg-red-100 text-red-900 border-red-300",
      disbursement: "bg-blue-100 text-blue-900 border-blue-300",
    };
    return map[type] || "bg-stone-100 text-stone-700 border-stone-200";
  };
  const wrapperColor = disbursement
    ? "border-blue-200"
    : overdue
    ? "border-amber-200"
    : "border-stone-200";
  const headBg = disbursement ? "bg-blue-50/60" : overdue ? "bg-amber-50/60" : "bg-stone-50";

  // Group payments by contract_id so the same contract shows once with a
  // dropdown revealing every individual payment for that contract.
  const groups = useMemo(() => {
    const map = new Map();
    for (const r of rows) {
      const key = r.contract_id || "—";
      const g = map.get(key) || {
        contract_id: key,
        items: [],
        total: 0,
        latest_date: "",
      };
      g.items.push(r);
      g.total += Number(r.amount || 0);
      if ((r.date || "") > g.latest_date) g.latest_date = r.date || "";
      map.set(key, g);
    }
    // Sort each group's items newest first
    for (const g of map.values()) {
      g.items.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
    }
    // Sort groups by most-recent activity
    return Array.from(map.values()).sort((a, b) => b.latest_date.localeCompare(a.latest_date));
  }, [rows]);

  const toggle = (key) => setExpanded((e) => ({ ...e, [key]: !e[key] }));

  const detailColSpan = disbursement ? 7 : 5;

  return (
    <div className={`rounded-lg border ${wrapperColor} bg-white overflow-x-auto`}>
      <table className="min-w-full text-sm" data-testid={testid}>
        <thead className={`${headBg} text-left`}>
          <tr>
            <Th className="w-10"></Th>
            <Th>{t("contract_number")}</Th>
            <Th right>Payments</Th>
            <Th right>{t("total")}</Th>
            <Th>Latest {t("date")}</Th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => {
            const isOpen = !!expanded[g.contract_id];
            const contract = contractById ? contractById(g.contract_id) : null;
            return (
              <Fragment key={g.contract_id}>
                <tr
                  key={`grp-${g.contract_id}`}
                  className="border-t border-stone-100 hover:bg-stone-50/50 cursor-pointer"
                  onClick={() => toggle(g.contract_id)}
                  data-testid={`payment-group-${g.contract_id}`}
                >
                  <Td>
                    <button
                      type="button"
                      className="inline-flex items-center justify-center w-6 h-6 rounded-md hover:bg-stone-200"
                      aria-label={isOpen ? "Collapse" : "Expand"}
                      data-testid={`payment-group-toggle-${g.contract_id}`}
                    >
                      {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </button>
                  </Td>
                  <Td className="font-medium whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span>{contractLabel(g.contract_id)}</span>
                      {!disbursement && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            const cn = contract?.contract_number || g.contract_id;
                            const url = `${API_BASE}/contracts/${g.contract_id}/payments-summary-pdf`;
                            onPreview && onPreview({
                              id: g.contract_id,
                              receipt_number: `${cn}-history`,
                              _url: url,
                              _title: `Payment History · ${cn}`,
                            });
                          }}
                          data-testid={`payment-history-btn-${g.contract_id}`}
                          title="Payment History PDF (all payments on this contract)"
                          className="inline-flex items-center justify-center w-6 h-6 rounded-md bg-[#4C7F62] text-white hover:bg-[#3F6B52] transition-colors"
                        >
                          <ScrollText className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  </Td>
                  <Td right className="tabular-nums">{g.items.length}</Td>
                  <Td right className="font-medium tabular-nums">${g.total.toLocaleString()}</Td>
                  <Td className="whitespace-nowrap text-stone-500">{g.latest_date || "—"}</Td>
                </tr>
                {isOpen && (
                  <tr key={`det-${g.contract_id}`} className="bg-stone-50/40">
                    <td colSpan="5" className="p-0">
                      <div className="overflow-x-auto">
                        <table className="min-w-full text-xs" data-testid={`payment-group-detail-${g.contract_id}`}>
                          <thead className="text-left">
                            <tr>
                              <SubTh>{t("receipt")}</SubTh>
                              <SubTh>{t("payment_type")}</SubTh>
                              <SubTh right>{t("amount")}</SubTh>
                              {disbursement && <SubTh right>{t("interest_per_month")}</SubTh>}
                              {disbursement && <SubTh>{t("due_date")}</SubTh>}
                              <SubTh>{t("date")}</SubTh>
                              <SubTh right>{t("actions")}</SubTh>
                            </tr>
                          </thead>
                          <tbody>
                            {g.items.map((r) => {
                              const perMonth = contract
                                ? Number(contract.per_month_interest ?? (Number(contract.loan_amount || 0) * Number(contract.interest_rate || 0) / 100)) || 0
                                : 0;
                              return (
                                <tr key={r.id} className="border-t border-stone-100">
                                  <SubTd className="font-medium" title={r.receipt_number}>{shortReceipt(r.receipt_number)}</SubTd>
                                  <SubTd>
                                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${typeBadge(r.type)}`}>
                                      {t(r.type) || r.type.replace(/_/g, " ")}
                                    </span>
                                  </SubTd>
                                  <SubTd right className="font-medium">${Number(r.amount).toLocaleString()}</SubTd>
                                  {disbursement && (
                                    <SubTd right className="text-amber-800">
                                      ${perMonth.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                      {contract ? <span className="ml-1 text-[10px] text-stone-500">({contract.interest_rate}%)</span> : null}
                                    </SubTd>
                                  )}
                                  {disbursement && (
                                    <SubTd>{contract?.due_date || "—"}</SubTd>
                                  )}
                                  <SubTd>{r.date}</SubTd>
                                  <SubTd right>
                                    <div className="flex justify-end gap-1.5">
                                      <button
                                        type="button"
                                        onClick={(ev) => { ev.stopPropagation(); onPreview?.(r); }}
                                        data-testid={`payment-pdf-${r.id}`}
                                        className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#DC2626] text-white hover:bg-[#B91C1C] transition-colors"
                                        title={t("preview") || "Preview"}
                                      >
                                        <Eye className="w-3.5 h-3.5" />
                                      </button>
                                      {isAdmin && (
                                        <button
                                          type="button"
                                          onClick={(ev) => { ev.stopPropagation(); onDelete?.(r); }}
                                          data-testid={`payment-delete-${r.id}`}
                                          className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-white border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors"
                                          title="Delete payment (admin only)"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                      )}
                                    </div>
                                  </SubTd>
                                </tr>
                              );
                            })}
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
              <td colSpan="5" className="p-8 text-center text-stone-500">
                No payments
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ModeChoice({ active, onClick, icon, title, hint, testid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testid}
      className={`w-full flex items-start gap-3 text-left rounded-md border px-3 py-2 transition-colors ${
        active
          ? "border-amber-500 bg-amber-50 ring-1 ring-amber-300"
          : "border-stone-200 bg-white hover:bg-stone-50"
      }`}
    >
      <div className={`mt-0.5 w-7 h-7 rounded-md flex items-center justify-center ${active ? "bg-amber-600 text-white" : "bg-stone-100 text-stone-600"}`}>
        {icon}
      </div>
      <div className="flex-1">
        <div className={`text-sm font-semibold ${active ? "text-amber-900" : "text-stone-800"}`}>{title}</div>
        <div className="text-xs text-stone-500">{hint}</div>
      </div>
    </button>
  );
}

function Field({ label, full, children }) {
  return (
    <div className={full ? "md:col-span-2 space-y-1.5" : "space-y-1.5"}>
      <Label className="text-xs uppercase tracking-wider text-stone-500">{label}</Label>
      {children}
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

function Td({ children, right, className = "" }) {
  return <td className={`px-3 py-3 ${right ? "text-right" : ""} ${className}`}>{children}</td>;
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
