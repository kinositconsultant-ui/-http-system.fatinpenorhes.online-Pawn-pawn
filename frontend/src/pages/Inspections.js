import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Plus,
  Wrench,
  Fuel,
  Droplets,
  BatteryCharging,
  Cog,
  Users as UsersIcon,
  CircleDollarSign,
  Pencil,
  Trash2,
  CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";

const CATEGORIES = [
  { value: "radiator", label: "Radiator", Icon: Droplets },
  { value: "oil", label: "Oil", Icon: Droplets },
  { value: "fuel", label: "Fuel", Icon: Fuel },
  { value: "battery", label: "Battery", Icon: BatteryCharging },
  { value: "lubricant", label: "Lubricant", Icon: Droplets },
  { value: "spare_part", label: "Spare Part", Icon: Cog },
  { value: "labor", label: "Labor", Icon: UsersIcon },
  { value: "other", label: "Other", Icon: Wrench },
];

const blank = {
  contract_id: "",
  category: "other",
  description: "",
  amount: "",
  incurred_date: new Date().toISOString().slice(0, 10),
  notes: "",
};

const fmtUSD = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(n || 0));

export default function Inspections() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [contracts, setContracts] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [editingId, setEditingId] = useState(null);
  const [reimburseFor, setReimburseFor] = useState(null); // row being reimbursed
  const [reimburseAmt, setReimburseAmt] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all"); // all | pending | reimbursed
  const [filterContract, setFilterContract] = useState("");

  const load = async () => {
    const [r, s, cs] = await Promise.all([
      api.get("/inspections"),
      api.get("/inspections/summary"),
      api.get("/contracts"),
    ]);
    setRows(r.data);
    setSummary(s.data);
    setContracts(cs.data);
  };

  useEffect(() => {
    load();
  }, []);

  const contractOptions = useMemo(
    () =>
      contracts.map((c) => ({
        value: c.id,
        label: `${c.contract_number} · ${c.item_type}`,
      })),
    [contracts]
  );

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (filterCategory !== "all" && r.category !== filterCategory) return false;
      if (filterStatus === "pending" && r.reimbursed) return false;
      if (filterStatus === "reimbursed" && !r.reimbursed) return false;
      if (
        filterContract &&
        !r.contract_number?.toLowerCase().includes(filterContract.toLowerCase())
      )
        return false;
      return true;
    });
  }, [rows, filterCategory, filterStatus, filterContract]);

  const onChange = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.contract_id) {
      toast.error("Choose a contract");
      return;
    }
    if (!form.amount || Number(form.amount) <= 0) {
      toast.error("Amount must be positive");
      return;
    }
    const payload = { ...form, amount: Number(form.amount) };
    try {
      if (editingId) {
        await api.put(`/inspections/${editingId}`, payload);
        toast.success("Inspection updated");
      } else {
        await api.post("/inspections", payload);
        toast.success("Inspection recorded — Cash on Hand debited");
      }
      setOpen(false);
      setEditingId(null);
      setForm(blank);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const startEdit = (r) => {
    setEditingId(r.id);
    setForm({
      contract_id: r.contract_id,
      category: r.category,
      description: r.description || "",
      amount: r.amount,
      incurred_date: r.incurred_date,
      notes: r.notes || "",
    });
    setOpen(true);
  };

  const del = async (r) => {
    if (!window.confirm(`Delete inspection expense of ${fmtUSD(r.amount)}?`)) return;
    try {
      await api.delete(`/inspections/${r.id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  const openReimburse = (r) => {
    setReimburseFor(r);
    setReimburseAmt(String(r.amount));
  };

  const doReimburse = async () => {
    if (!reimburseFor) return;
    const amt = Number(reimburseAmt);
    if (!amt || amt <= 0) {
      toast.error("Enter a positive amount");
      return;
    }
    try {
      await api.post(`/inspections/${reimburseFor.id}/reimburse`, {
        reimbursed_amount: amt,
      });
      toast.success("Reimbursement recorded — Cash on Hand credited");
      setReimburseFor(null);
      setReimburseAmt("");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Reimburse failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="inspections-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("inspections") || "Operations"}</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
            Inspection Expenses
          </h1>
          <p className="text-sm text-stone-600 mt-1 max-w-xl">
            Track money spent to inspect or service pawned items (radiator, oil,
            fuel, battery, lubricants, spare parts). Each entry debits Cash on
            Hand; when the client reimburses, the amount is credited back.
          </p>
        </div>
        <Dialog
          open={open}
          onOpenChange={(o) => {
            setOpen(o);
            if (!o) {
              setEditingId(null);
              setForm(blank);
            }
          }}
        >
          <DialogTrigger asChild>
            <Button
              className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
              data-testid="inspection-new-btn"
            >
              <Plus className="w-4 h-4 mr-1" /> New Inspection
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>
                {editingId ? "Edit inspection expense" : "New inspection expense"}
              </DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="md:col-span-2">
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Contract
                </Label>
                <Select
                  value={form.contract_id}
                  onValueChange={(v) => onChange("contract_id", v)}
                >
                  <SelectTrigger data-testid="inspection-contract">
                    <SelectValue placeholder="Choose contract" />
                  </SelectTrigger>
                  <SelectContent className="max-h-64">
                    {contractOptions.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Category
                </Label>
                <Select
                  value={form.category}
                  onValueChange={(v) => onChange("category", v)}
                >
                  <SelectTrigger data-testid="inspection-category">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Amount ($)
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.amount}
                  onChange={(e) => onChange("amount", e.target.value)}
                  data-testid="inspection-amount"
                />
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Date
                </Label>
                <Input
                  type="date"
                  value={form.incurred_date}
                  onChange={(e) => onChange("incurred_date", e.target.value)}
                  data-testid="inspection-date"
                />
              </div>
              <div className="md:col-span-2">
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Description
                </Label>
                <Input
                  value={form.description}
                  onChange={(e) => onChange("description", e.target.value)}
                  placeholder="e.g. Radiator flush + coolant top-up"
                  data-testid="inspection-desc"
                />
              </div>
              <div className="md:col-span-2">
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Notes
                </Label>
                <Input
                  value={form.notes}
                  onChange={(e) => onChange("notes", e.target.value)}
                  data-testid="inspection-notes"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
                onClick={submit}
                data-testid="inspection-save"
              >
                {editingId ? "Update" : "Save"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </header>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiTile
          label="Incurred (lifetime)"
          value={fmtUSD(summary?.incurred_total)}
          tone="text-rose-800"
          bg="bg-rose-50 border-rose-200"
          testid="kpi-incurred"
        />
        <KpiTile
          label="Reimbursed"
          value={fmtUSD(summary?.reimbursed_total)}
          tone="text-emerald-800"
          bg="bg-emerald-50 border-emerald-200"
          testid="kpi-reimbursed"
        />
        <KpiTile
          label="Net Cost"
          value={fmtUSD(summary?.net_cost)}
          tone="text-[#1B2D5C]"
          bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25"
          testid="kpi-net"
        />
        <KpiTile
          label="Pending Reimbursement"
          value={String(summary?.pending_count ?? 0)}
          tone="text-amber-800"
          bg="bg-amber-50 border-amber-200"
          testid="kpi-pending"
        />
      </div>

      {/* Filters */}
      <Card className="p-3 md:p-4 border border-stone-200 shadow-none rounded-lg bg-white flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[150px]">
          <Label className="text-xs uppercase tracking-wider text-stone-500">
            Contract search
          </Label>
          <Input
            value={filterContract}
            onChange={(e) => setFilterContract(e.target.value)}
            placeholder="CT-2026-…"
            data-testid="filter-contract"
          />
        </div>
        <div className="min-w-[150px]">
          <Label className="text-xs uppercase tracking-wider text-stone-500">
            Category
          </Label>
          <Select value={filterCategory} onValueChange={setFilterCategory}>
            <SelectTrigger data-testid="filter-category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {CATEGORIES.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-[150px]">
          <Label className="text-xs uppercase tracking-wider text-stone-500">
            Status
          </Label>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger data-testid="filter-status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="pending">Pending reimbursement</SelectItem>
              <SelectItem value="reimbursed">Reimbursed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </Card>

      {/* Table */}
      <Card className="p-0 border border-stone-200 shadow-none rounded-lg bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="inspections-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>Date</Th>
              <Th>Contract</Th>
              <Th>Category</Th>
              <Th>Description</Th>
              <Th right>Amount</Th>
              <Th>Status</Th>
              <Th right>Actions</Th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td className="p-6 text-center text-stone-400" colSpan={7}>
                  No inspection expenses yet.
                </td>
              </tr>
            )}
            {filtered.map((r) => {
              const cat = CATEGORIES.find((c) => c.value === r.category);
              const Icon = cat?.Icon || Wrench;
              return (
                <tr
                  key={r.id}
                  className="border-t border-stone-100 hover:bg-stone-50/50"
                  data-testid={`inspection-row-${r.id}`}
                >
                  <Td>{r.incurred_date}</Td>
                  <Td>
                    <span className="font-mono text-xs">{r.contract_number}</span>
                  </Td>
                  <Td>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200 text-xs">
                      <Icon className="w-3 h-3" />
                      {cat?.label || r.category}
                    </span>
                  </Td>
                  <Td>
                    <div className="max-w-[280px] truncate" title={r.description}>
                      {r.description || "—"}
                    </div>
                  </Td>
                  <Td right>
                    <span className="font-semibold tabular-nums">
                      {fmtUSD(r.amount)}
                    </span>
                  </Td>
                  <Td>
                    {r.reimbursed ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 text-xs">
                        <CheckCircle2 className="w-3 h-3" />
                        Reimbursed {fmtUSD(r.reimbursed_amount)}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300 text-xs">
                        <CircleDollarSign className="w-3 h-3" />
                        Pending
                      </span>
                    )}
                  </Td>
                  <Td right>
                    <div className="inline-flex gap-1">
                      {!r.reimbursed && (
                        <button
                          className="p-1.5 rounded-md bg-emerald-100 hover:bg-emerald-200 text-emerald-700 border border-emerald-300"
                          onClick={() => openReimburse(r)}
                          title="Mark reimbursed"
                          data-testid={`inspection-reimburse-${r.id}`}
                        >
                          <CheckCircle2 className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        className="p-1.5 rounded-md hover:bg-stone-100 text-stone-600"
                        onClick={() => startEdit(r)}
                        title="Edit"
                        data-testid={`inspection-edit-${r.id}`}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        className="p-1.5 rounded-md hover:bg-rose-100 text-rose-700"
                        onClick={() => del(r)}
                        title="Delete"
                        data-testid={`inspection-delete-${r.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      {/* Reimburse dialog */}
      <Dialog open={!!reimburseFor} onOpenChange={(o) => !o && setReimburseFor(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Mark as reimbursed</DialogTitle>
          </DialogHeader>
          {reimburseFor && (
            <div className="space-y-3">
              <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm space-y-1">
                <div>
                  <span className="text-stone-500">Contract:</span>{" "}
                  <span className="font-mono">{reimburseFor.contract_number}</span>
                </div>
                <div>
                  <span className="text-stone-500">Category:</span>{" "}
                  {reimburseFor.category}
                </div>
                <div>
                  <span className="text-stone-500">Original:</span>{" "}
                  <span className="font-semibold">{fmtUSD(reimburseFor.amount)}</span>
                </div>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">
                  Reimbursed amount ($)
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  value={reimburseAmt}
                  onChange={(e) => setReimburseAmt(e.target.value)}
                  data-testid="reimburse-amount"
                  autoFocus
                />
                <p className="text-[11px] text-stone-500 mt-1">
                  Cash on Hand will be credited by this amount.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setReimburseFor(null)}>
              Cancel
            </Button>
            <Button
              className="bg-emerald-700 hover:bg-emerald-800"
              onClick={doReimburse}
              data-testid="reimburse-save"
            >
              <CheckCircle2 className="w-4 h-4 mr-1" /> Reimburse
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function KpiTile({ label, value, tone, bg, testid }) {
  return (
    <div className={`rounded-lg border ${bg} p-3 md:p-4`} data-testid={testid}>
      <div className="text-[11px] uppercase tracking-wide text-stone-500">{label}</div>
      <div className={`font-display text-xl md:text-2xl font-semibold mt-1 ${tone}`}>
        {value}
      </div>
    </div>
  );
}

function Th({ children, right }) {
  return (
    <th
      className={`px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </th>
  );
}

function Td({ children, right, className = "" }) {
  return (
    <td
      className={`px-3 py-2 whitespace-nowrap ${
        right ? "text-right" : ""
      } ${className}`}
    >
      {children}
    </td>
  );
}
