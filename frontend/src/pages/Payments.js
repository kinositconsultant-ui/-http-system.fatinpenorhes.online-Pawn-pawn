import { useEffect, useMemo, useState } from "react";
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
import { Plus, FileDown, AlertTriangle, Coins, Banknote, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { shortContract, shortReceipt } from "../lib/docNumbers";

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
  const [rows, setRows] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);

  // Overdue dialog state
  const [odOpen, setOdOpen] = useState(false);
  const [odContractId, setOdContractId] = useState("");
  const [odMode, setOdMode] = useState("overdue_full");
  const [odDate, setOdDate] = useState(new Date().toISOString().slice(0, 10));

  const load = async () => {
    const [p, c] = await Promise.all([api.get("/payments"), api.get("/contracts")]);
    setRows(p.data);
    setContracts(c.data);
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
  const selectedContract = contracts.find((c) => c.id === form.contract_id);
  const overdueContracts = useMemo(
    () => contracts.filter((c) => c.status === "overdue" || c.status === "auction_ready"),
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

  const overduePayments = rows.filter((r) =>
    ["overdue_full", "overdue_interest_pen", "overdue_penalty_only"].includes(r.type)
  );
  const regularPayments = rows.filter(
    (r) => !["overdue_full", "overdue_interest_pen", "overdue_penalty_only", "disbursement"].includes(r.type)
  );
  const disbursements = rows.filter((r) => r.type === "disbursement");

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
              if (!o) setForm(blank);
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
            <DialogContent className="max-w-xl">
              <DialogHeader>
                <DialogTitle>{t("new_payment")}</DialogTitle>
                <DialogDescription className="sr-only">
                  Record a new client payment against an active or overdue contract.
                </DialogDescription>
              </DialogHeader>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field label={t("contract_number")} full>
                  <Select
                    value={form.contract_id}
                    onValueChange={(v) => onChange("contract_id", v)}
                  >
                    <SelectTrigger data-testid="payment-contract">
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {contracts
                        .filter((c) => ["active", "overdue", "auction_ready"].includes(c.status))
                        .map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.contract_number} · ${Number(c.remaining_balance || 0).toLocaleString()} left
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </Field>
                {selectedContract && (
                  <div className="md:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm bg-stone-50 border border-stone-100 rounded-md p-3">
                    <div>
                      <div className="text-eyebrow">{t("interest_left")}</div>
                      <div className="font-display text-lg text-amber-700" data-testid="np-interest-remaining">
                        ${Number(selectedContract.interest_remaining || 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-eyebrow">{t("total_due")}</div>
                      <div className="font-display text-lg" data-testid="np-total-due">
                        ${Number(selectedContract.total_due || 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-eyebrow">{t("paid_amount")}</div>
                      <div className="font-display text-lg" data-testid="np-paid">
                        ${Number(selectedContract.paid_amount || 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-eyebrow">{t("remaining_balance")}</div>
                      <div className="font-display text-lg text-[#C17767]" data-testid="np-remaining">
                        ${Number(selectedContract.remaining_balance || 0).toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}
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
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>
                  {t("cancel")}
                </Button>
                <Button
                  onClick={submit}
                  className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
                  data-testid="payment-save"
                >
                  {t("save")}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </header>

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
          <PaymentsTable rows={regularPayments} contractLabel={contractLabel} t={t} testid="payments-table" isAdmin={isAdmin} onDelete={deletePayment} />
        </TabsContent>
        <TabsContent value="overdue">
          <PaymentsTable rows={overduePayments} contractLabel={contractLabel} t={t} testid="overdue-payments-table" overdue isAdmin={isAdmin} onDelete={deletePayment} />
        </TabsContent>
        <TabsContent value="disbursements">
          <PaymentsTable rows={disbursements} contractLabel={contractLabel} contractById={contractById} t={t} testid="disbursements-table" disbursement isAdmin={isAdmin} onDelete={deletePayment} />
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
    </div>
  );
}

function PaymentsTable({ rows, contractLabel, contractById, t, testid, overdue = false, disbursement = false, isAdmin = false, onDelete }) {
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
  return (
    <div className={`rounded-lg border ${wrapperColor} bg-white overflow-x-auto`}>
      <table className="min-w-full text-sm" data-testid={testid}>
        <thead className={`${headBg} text-left`}>
          <tr>
            <Th>{t("receipt")}</Th>
            <Th>{t("contract_number")}</Th>
            <Th>{t("payment_type")}</Th>
            <Th right>{t("amount")}</Th>
            {disbursement && <Th right>{t("interest_per_month")}</Th>}
            {disbursement && <Th>{t("due_date")}</Th>}
            <Th>{t("date")}</Th>
            <Th right>{t("actions")}</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const contract = contractById ? contractById(r.contract_id) : null;
            const perMonth = contract
              ? Number(contract.per_month_interest ?? (Number(contract.loan_amount || 0) * Number(contract.interest_rate || 0) / 100)) || 0
              : 0;
            return (
            <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50/50">
              <Td className="font-medium whitespace-nowrap" title={r.receipt_number}>{shortReceipt(r.receipt_number)}</Td>
              <Td className="whitespace-nowrap">{contractLabel(r.contract_id)}</Td>
              <Td className="whitespace-nowrap">
                <span className={`text-xs px-2 py-0.5 rounded-full border ${typeBadge(r.type)}`}>
                  {t(r.type) || r.type.replace(/_/g, " ")}
                </span>
              </Td>
              <Td right className="whitespace-nowrap font-medium">${Number(r.amount).toLocaleString()}</Td>
              {disbursement && (
                <Td right className="whitespace-nowrap text-amber-800"
                    title={contract
                      ? `Current-month interest (Rule B: hybrid). Principal remaining ×  ${contract.interest_rate}% = $${perMonth.toFixed(2)}`
                      : ""}>
                  ${perMonth.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  {contract ? <span className="ml-1 text-[10px] text-stone-500">({contract.interest_rate}%)</span> : null}
                </Td>
              )}
              {disbursement && (
                <Td className="whitespace-nowrap text-xs">{contract?.due_date || "—"}</Td>
              )}
              <Td className="whitespace-nowrap">{r.date}</Td>
              <Td right>
                <div className="flex justify-end gap-1.5">
                  <a
                    href={`${API_BASE}/payments/${r.id}/pdf`}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`payment-pdf-${r.id}`}
                    className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#DC2626] text-white hover:bg-[#B91C1C] transition-colors"
                    title={t("download_pdf")}
                  >
                    <FileDown className="w-3.5 h-3.5" />
                  </a>
                  {isAdmin && (
                    <button
                      type="button"
                      onClick={() => onDelete?.(r)}
                      data-testid={`payment-delete-${r.id}`}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-white border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors"
                      title="Delete payment (admin only)"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </Td>
            </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={disbursement ? 8 : 6} className="p-8 text-center text-stone-500">
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

function Td({ children, right, className = "" }) {
  return <td className={`px-3 py-3 ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}
