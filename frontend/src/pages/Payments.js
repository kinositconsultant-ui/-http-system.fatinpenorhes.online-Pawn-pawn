import { useEffect, useState } from "react";
import { api, API_BASE } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
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
import { Plus, FileDown } from "lucide-react";
import { toast } from "sonner";

const blank = {
  contract_id: "",
  amount: "",
  type: "partial",
  date: new Date().toISOString().slice(0, 10),
  notes: "",
};

export default function Payments() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);

  const load = async () => {
    const [p, c] = await Promise.all([api.get("/payments"), api.get("/contracts")]);
    setRows(p.data);
    setContracts(c.data);
  };
  useEffect(() => {
    load();
  }, []);

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
    return c ? `${c.contract_number}` : id;
  };
  const selectedContract = contracts.find((c) => c.id === form.contract_id);

  return (
    <div className="space-y-6" data-testid="payments-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("payments")}</div>
          <h1 className="font-display text-4xl font-semibold mt-1">{t("payments")}</h1>
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
              data-testid="payment-new-btn"
            >
              <Plus className="w-4 h-4 mr-1" /> {t("new_payment")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-xl">
            <DialogHeader>
              <DialogTitle>{t("new_payment")}</DialogTitle>
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
                      .filter((c) => ["active", "overdue"].includes(c.status))
                      .map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.contract_number} · ${Number(c.remaining_balance || 0).toLocaleString()} left
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </Field>
              {selectedContract && (
                <div className="md:col-span-2 grid grid-cols-3 gap-3 text-sm bg-stone-50 border border-stone-100 rounded-md p-3">
                  <div>
                    <div className="text-eyebrow">{t("total_due")}</div>
                    <div className="font-display text-lg">
                      ${Number(selectedContract.total_due || 0).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-eyebrow">{t("paid_amount")}</div>
                    <div className="font-display text-lg">
                      ${Number(selectedContract.paid_amount || 0).toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-eyebrow">{t("remaining_balance")}</div>
                    <div className="font-display text-lg text-[#C17767]">
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
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="payments-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>Receipt</Th>
              <Th>{t("contract_number")}</Th>
              <Th>{t("payment_type")}</Th>
              <Th right>{t("amount")}</Th>
              <Th>{t("date")}</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100 hover:bg-stone-50/50">
                <Td className="font-medium whitespace-nowrap">{r.receipt_number}</Td>
                <Td className="whitespace-nowrap">{contractLabel(r.contract_id)}</Td>
                <Td className="whitespace-nowrap">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${
                    r.type === "full" ? "bg-emerald-50 text-emerald-800 border-emerald-200" :
                    r.type === "interest_only" ? "bg-amber-50 text-amber-800 border-amber-200" :
                    "bg-stone-100 text-stone-700 border-stone-200"
                  }`}>
                    {r.type.replace("_", " ")}
                  </span>
                </Td>
                <Td right className="whitespace-nowrap font-medium">${Number(r.amount).toLocaleString()}</Td>
                <Td className="whitespace-nowrap">{r.date}</Td>
                <Td right>
                  <div className="flex justify-end">
                    <a
                      href={`${API_BASE}/payments/${r.id}/pdf`}
                      target="_blank"
                      rel="noreferrer"
                      data-testid={`payment-pdf-${r.id}`}
                      className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-[#1B2D5C] text-white hover:bg-[#0F1B3A] transition-colors"
                      title={t("download_pdf")}
                    >
                      <FileDown className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan="6" className="p-8 text-center text-stone-500">
                  No payments
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
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
