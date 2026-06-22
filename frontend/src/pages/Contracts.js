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
import { Plus, Trash2, FileDown, Gavel, MessageCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";

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

const DEFAULT_RATE_FALLBACK = { car: 10, motorcycle: 15, electronic: 15 };

export default function Contracts() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [clients, setClients] = useState([]);
  const [itemsByKind, setItemsByKind] = useState({ car: [], motorcycle: [], electronic: [] });
  const [defaults, setDefaults] = useState(DEFAULT_RATE_FALLBACK);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);

  const load = async () => {
    const [c, cl, cars, mc, el, s] = await Promise.all([
      api.get("/contracts"),
      api.get("/clients"),
      api.get("/items/car"),
      api.get("/items/motorcycle"),
      api.get("/items/electronic"),
      api.get("/settings"),
    ]);
    setRows(c.data);
    setClients(cl.data);
    setItemsByKind({ car: cars.data, motorcycle: mc.data, electronic: el.data });
    setDefaults({
      car: s.data.interest_rate_car ?? 10,
      motorcycle: s.data.interest_rate_motorcycle ?? 15,
      electronic: s.data.interest_rate_electronic ?? 15,
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

  const sendWhatsApp = async (id, language) => {
    try {
      const { data } = await api.post("/whatsapp/send", { contract_id: id, language });
      const note = data.status === "mocked"
        ? "WhatsApp (mocked — set token in Settings)"
        : `WhatsApp ${data.status}`;
      toast.success(note);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
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

  const availableItems = itemsByKind[form.item_type]?.filter(
    (i) => i.status === "in_stock" || !i.status
  );

  return (
    <div className="space-y-6" data-testid="contracts-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("contracts")}</div>
          <h1 className="font-display text-4xl font-semibold mt-1">{t("contracts")}</h1>
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
              className="bg-[#2F4F4F] hover:bg-[#1D3333]"
              data-testid="contract-new-btn"
            >
              <Plus className="w-4 h-4 mr-1" /> {t("new_contract")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{t("new_contract")}</DialogTitle>
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
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {t("cancel")}
              </Button>
              <Button
                onClick={submit}
                className="bg-[#2F4F4F] hover:bg-[#1D3333]"
                data-testid="contract-save"
              >
                {t("save")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="contracts-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>{t("contract_number")}</Th>
              <Th>{t("client")}</Th>
              <Th>{t("item")}</Th>
              <Th right>{t("loan_amount")}</Th>
              <Th right>{t("interest_rate")}</Th>
              <Th>{t("contract_date")}</Th>
              <Th>{t("due_date")}</Th>
              <Th right>{t("remaining_balance")}</Th>
              <Th right>{t("penalty")}</Th>
              <Th>{t("status")}</Th>
              <Th right>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100">
                <Td className="font-medium">{r.contract_number}</Td>
                <Td>{clientName(r.client_id)}</Td>
                <Td>
                  <span className="text-xs uppercase tracking-wider text-stone-500 mr-1">
                    {r.item_type}
                  </span>
                  {itemLabel(r.item_type, r.item_id)}
                </Td>
                <Td right>${Number(r.loan_amount).toLocaleString()}</Td>
                <Td right>{r.interest_rate}%</Td>
                <Td>{r.contract_date}</Td>
                <Td>{r.due_date}</Td>
                <Td right>${Number(r.remaining_balance ?? 0).toLocaleString()}</Td>
                <Td right className={Number(r.penalty || 0) > 0 ? "text-[#993333] font-medium" : "text-stone-400"} >
                  ${Number(r.penalty || 0).toLocaleString()}
                </Td>
                <Td>
                  <StatusBadge status={r.status} />
                </Td>
                <Td right>
                  <div className="flex justify-end gap-2">
                    <a
                      href={`${API_BASE}/contracts/${r.id}/pdf`}
                      target="_blank"
                      rel="noreferrer"
                      data-testid={`contract-pdf-${r.id}`}
                      className="p-1 hover:text-[#2F4F4F]"
                    >
                      <FileDown className="w-4 h-4" />
                    </a>
                    {r.status === "overdue" && (
                      <button
                        onClick={() => openReactivate(r)}
                        data-testid={`contract-reactivate-${r.id}`}
                        className="p-1 hover:text-[#4C7F62]"
                        title={t("reactivate")}
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                    )}
                    {["active", "overdue"].includes(r.status) && (
                      <button
                        onClick={() => moveToAuction(r.id)}
                        data-testid={`contract-auction-${r.id}`}
                        className="p-1 hover:text-[#C17767]"
                        title={t("move_to_auction")}
                      >
                        <Gavel className="w-4 h-4" />
                      </button>
                    )}
                    {["active", "overdue"].includes(r.status) && (
                      <button
                        onClick={() => sendWhatsApp(r.id, "en")}
                        data-testid={`contract-whatsapp-${r.id}`}
                        className="p-1 hover:text-[#4C7F62]"
                        title={t("send_whatsapp")}
                      >
                        <MessageCircle className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => remove(r.id)}
                      data-testid={`contract-delete-${r.id}`}
                      className="p-1 hover:text-[#993333]"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan="11" className="p-8 text-center text-stone-500">
                  No contracts
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Reactivate dialog */}
      <Dialog open={reactOpen} onOpenChange={setReactOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("reactivate_contract")}</DialogTitle>
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
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    active: "bg-emerald-50 text-emerald-800 border-emerald-200",
    overdue: "bg-red-50 text-red-800 border-red-200",
    redeemed: "bg-stone-100 text-stone-700 border-stone-200",
    auction: "bg-orange-50 text-orange-800 border-orange-200",
  };
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full border ${
        map[status] || "bg-stone-100 text-stone-700 border-stone-200"
      }`}
    >
      {status}
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
      className={`px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}

function Td({ children, right, className = "" }) {
  return <td className={`px-4 py-3 ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}
