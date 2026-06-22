import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
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
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../components/ui/tabs";
import {
  Plus, Trash2, Pencil, Wallet, Landmark, Receipt, TrendingUp, ArrowDownCircle,
} from "lucide-react";
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend,
} from "recharts";
import { toast } from "sonner";

const fmt = (v) =>
  `$${Number(v ?? 0).toLocaleString("en-US", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })}`;

const PIE_COLORS = ["#1B2D5C", "#C17767", "#4C7F62", "#993333", "#8F9779", "#7C6BB0", "#D4A05E", "#475569"];

export default function Finance() {
  const { t } = useLang();
  const [summary, setSummary] = useState(null);
  const [sources, setSources] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [categories, setCategories] = useState([]);

  const load = useCallback(async () => {
    const [s, srcs, exps, cats] = await Promise.all([
      api.get("/finance/summary"),
      api.get("/funding-sources"),
      api.get("/expenses"),
      api.get("/expense-categories"),
    ]);
    setSummary(s.data);
    setSources(srcs.data);
    setExpenses(exps.data);
    setCategories(cats.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-8" data-testid="finance-root">
      <header>
        <div className="text-eyebrow">Treasury</div>
        <h1 className="font-display text-4xl font-semibold mt-1">Finance</h1>
      </header>

      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Cash on Hand" value={summary ? fmt(summary.cash_on_hand) : "…"}
             Icon={Wallet} tone={Number(summary?.cash_on_hand || 0) >= 0 ? "text-emerald-700" : "text-red-700"}
             testid="kpi-cash-on-hand" />
        <Kpi label="Capital Outstanding" value={summary ? fmt(summary.capital_outstanding) : "…"}
             Icon={Landmark} tone="text-[#1B2D5C]" testid="kpi-capital-outstanding" />
        <Kpi label="Expenses (Lifetime)" value={summary ? fmt(summary.expenses_total) : "…"}
             Icon={Receipt} tone="text-[#C17767]" testid="kpi-expenses-total" />
        <Kpi label="Net Profit" value={summary ? fmt(summary.net_profit) : "…"}
             Icon={TrendingUp} tone={Number(summary?.net_profit || 0) >= 0 ? "text-emerald-700" : "text-red-700"}
             testid="kpi-net-profit" />
      </div>

      {/* Cash flow + Expenses charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white">
          <div className="text-eyebrow mb-3">Cash Flow Snapshot</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={[
                { k: "Capital In", v: summary?.capital_received || 0 },
                { k: "Client Pay", v: summary?.client_payments || 0 },
                { k: "Auction", v: summary?.auction_sales || 0 },
                { k: "Loans Out", v: -(summary?.loans_disbursed || 0) },
                { k: "Expenses", v: -(summary?.expenses_total || 0) },
                { k: "Cap. Repaid", v: -(summary?.capital_repaid || 0) },
              ]}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" vertical={false} />
                <XAxis dataKey="k" stroke="#57534E" tick={{ fontSize: 11 }} />
                <YAxis stroke="#57534E" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E7E5E4", fontSize: 12 }}
                         formatter={(v) => fmt(Math.abs(v))} />
                <Bar dataKey="v" radius={[6, 6, 0, 0]}>
                  {[0,1,2,3,4,5].map((i) => (
                    <Cell key={i} fill={i < 3 ? "#1B2D5C" : "#C17767"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white">
          <div className="text-eyebrow mb-3">Expenses by Category (lifetime)</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={summary?.expenses_by_category || []}
                  dataKey="amount"
                  nameKey="category"
                  innerRadius={55}
                  outerRadius={100}
                  paddingAngle={2}
                >
                  {(summary?.expenses_by_category || []).map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => fmt(v)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Tabs: Capital + Expenses */}
      <Tabs defaultValue="capital" data-testid="finance-tabs">
        <TabsList>
          <TabsTrigger value="capital" data-testid="finance-tab-capital">
            <Landmark className="w-4 h-4 mr-2" /> Capital Sources
          </TabsTrigger>
          <TabsTrigger value="expenses" data-testid="finance-tab-expenses">
            <ArrowDownCircle className="w-4 h-4 mr-2" /> Expenses
          </TabsTrigger>
        </TabsList>
        <TabsContent value="capital">
          <CapitalSection sources={sources} reload={load} />
        </TabsContent>
        <TabsContent value="expenses">
          <ExpensesSection expenses={expenses} categories={categories} reload={load} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Kpi({ label, value, Icon, tone = "text-stone-900", testid }) {
  return (
    <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white" data-testid={testid}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-eyebrow">{label}</div>
          <div className={`font-display text-3xl font-semibold mt-3 ${tone}`}>{value}</div>
        </div>
        <Icon className={`w-6 h-6 ${tone}`} />
      </div>
    </Card>
  );
}

/* ---------- Capital Sources ---------- */
const blankSource = {
  name: "", source_type: "bank", principal_amount: "", interest_rate: 0,
  interest_period: "monthly", start_date: new Date().toISOString().slice(0, 10),
  due_date: "", notes: "",
};

function CapitalSection({ sources, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blankSource);
  const [editingId, setEditingId] = useState(null);
  const [repOpen, setRepOpen] = useState(false);
  const [repFor, setRepFor] = useState(null);
  const [repForm, setRepForm] = useState({ amount: "", date: new Date().toISOString().slice(0, 10), notes: "" });

  const submit = async () => {
    try {
      const payload = { ...form, principal_amount: Number(form.principal_amount), interest_rate: Number(form.interest_rate || 0) };
      if (editingId) await api.put(`/funding-sources/${editingId}`, payload);
      else await api.post("/funding-sources", payload);
      toast.success("Saved");
      setOpen(false); setForm(blankSource); setEditingId(null);
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };
  const edit = (s) => { setForm({ ...blankSource, ...s }); setEditingId(s.id); setOpen(true); };
  const remove = async (id) => {
    if (!window.confirm("Delete funding source?")) return;
    try { await api.delete(`/funding-sources/${id}`); reload(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const submitRep = async () => {
    try {
      await api.post(`/funding-sources/${repFor.id}/repayments`, {
        source_id: repFor.id, amount: Number(repForm.amount), date: repForm.date, notes: repForm.notes,
      });
      toast.success("Repayment recorded");
      setRepOpen(false); setRepForm({ amount: "", date: new Date().toISOString().slice(0, 10), notes: "" });
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-4 mt-4">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { setForm(blankSource); setEditingId(null); } }}>
          <DialogTrigger asChild>
            <Button className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="capital-new-btn">
              <Plus className="w-4 h-4 mr-1" /> New Source
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-xl">
            <DialogHeader><DialogTitle>{editingId ? "Edit" : "New"} Capital Source</DialogTitle></DialogHeader>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FF label="Name" full>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="capital-name" />
              </FF>
              <FF label="Type">
                <Select value={form.source_type} onValueChange={(v) => setForm({ ...form, source_type: v })}>
                  <SelectTrigger data-testid="capital-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["bank", "company", "personal", "partner", "other"].map((x) => (
                      <SelectItem key={x} value={x}>{x}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FF>
              <FF label="Principal Amount (USD)">
                <Input type="number" step="0.01" value={form.principal_amount} onChange={(e) => setForm({ ...form, principal_amount: e.target.value })} data-testid="capital-principal" />
              </FF>
              <FF label="Interest Rate %">
                <Input type="number" step="0.01" value={form.interest_rate} onChange={(e) => setForm({ ...form, interest_rate: e.target.value })} data-testid="capital-rate" />
              </FF>
              <FF label="Interest Period">
                <Select value={form.interest_period} onValueChange={(v) => setForm({ ...form, interest_period: v })}>
                  <SelectTrigger data-testid="capital-period"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="yearly">Yearly</SelectItem>
                    <SelectItem value="none">None</SelectItem>
                  </SelectContent>
                </Select>
              </FF>
              <FF label="Start Date">
                <Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} data-testid="capital-start" />
              </FF>
              <FF label="Due Date (optional)">
                <Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} data-testid="capital-due" />
              </FF>
              <FF label="Notes" full>
                <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </FF>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={submit} className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="capital-save">Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="capital-table">
          <thead className="bg-stone-50 text-left">
            <tr>{["Name", "Type", "Principal", "Rate", "Repaid", "Outstanding", "Start", "Due", "Actions"].map((h) => (
              <th key={h} className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id} className="border-t border-stone-100">
                <td className="px-4 py-3 font-medium">{s.name}</td>
                <td className="px-4 py-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">{s.source_type}</span>
                </td>
                <td className="px-4 py-3">{fmt(s.principal_amount)}</td>
                <td className="px-4 py-3">{s.interest_rate}% / {s.interest_period}</td>
                <td className="px-4 py-3">{fmt(s.total_repaid)}</td>
                <td className="px-4 py-3 font-medium text-[#C17767]">{fmt(s.outstanding)}</td>
                <td className="px-4 py-3">{s.start_date}</td>
                <td className="px-4 py-3">{s.due_date || "—"}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button onClick={() => { setRepFor(s); setRepOpen(true); }} data-testid={`capital-repay-${s.id}`}
                            className="text-xs px-2 py-1 rounded-md bg-[#1B2D5C] text-white hover:bg-[#0F1B3A]">Repay</button>
                    <button onClick={() => edit(s)} className="p-1 hover:text-[#1B2D5C]" data-testid={`capital-edit-${s.id}`}>
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => remove(s.id)} className="p-1 hover:text-[#993333]" data-testid={`capital-delete-${s.id}`}>
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {sources.length === 0 && (
              <tr><td colSpan="9" className="p-8 text-center text-stone-500">No capital sources yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={repOpen} onOpenChange={setRepOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Record Repayment — {repFor?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <FF label="Amount">
              <Input type="number" step="0.01" value={repForm.amount} onChange={(e) => setRepForm({ ...repForm, amount: e.target.value })} data-testid="capital-rep-amount" />
            </FF>
            <FF label="Date">
              <Input type="date" value={repForm.date} onChange={(e) => setRepForm({ ...repForm, date: e.target.value })} data-testid="capital-rep-date" />
            </FF>
            <FF label="Notes">
              <Textarea value={repForm.notes} onChange={(e) => setRepForm({ ...repForm, notes: e.target.value })} />
            </FF>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRepOpen(false)}>Cancel</Button>
            <Button onClick={submitRep} className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="capital-rep-save">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------- Expenses ---------- */
const blankExpense = {
  category: "Salary", amount: "", date: new Date().toISOString().slice(0, 10),
  paid_to: "", description: "", payment_method: "cash", receipt_url: "",
};

function ExpensesSection({ expenses, categories, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blankExpense);
  const [editingId, setEditingId] = useState(null);

  const submit = async () => {
    try {
      const payload = { ...form, amount: Number(form.amount) };
      if (editingId) await api.put(`/expenses/${editingId}`, payload);
      else await api.post("/expenses", payload);
      toast.success("Saved");
      setOpen(false); setForm(blankExpense); setEditingId(null);
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const edit = (e) => { setForm({ ...blankExpense, ...e }); setEditingId(e.id); setOpen(true); };
  const remove = async (id) => {
    if (!window.confirm("Delete expense?")) return;
    try { await api.delete(`/expenses/${id}`); reload(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-4 mt-4">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { setForm(blankExpense); setEditingId(null); } }}>
          <DialogTrigger asChild>
            <Button className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="expense-new-btn">
              <Plus className="w-4 h-4 mr-1" /> New Expense
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-xl">
            <DialogHeader><DialogTitle>{editingId ? "Edit" : "New"} Expense</DialogTitle></DialogHeader>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FF label="Category">
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                  <SelectTrigger data-testid="expense-category"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </FF>
              <FF label="Amount (USD)">
                <Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} data-testid="expense-amount" />
              </FF>
              <FF label="Date">
                <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="expense-date" />
              </FF>
              <FF label="Payment Method">
                <Select value={form.payment_method} onValueChange={(v) => setForm({ ...form, payment_method: v })}>
                  <SelectTrigger data-testid="expense-method"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["cash", "bank", "mobile", "other"].map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}
                  </SelectContent>
                </Select>
              </FF>
              <FF label="Paid To">
                <Input value={form.paid_to} onChange={(e) => setForm({ ...form, paid_to: e.target.value })} data-testid="expense-paid-to" />
              </FF>
              <FF label="Description" full>
                <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="expense-description" />
              </FF>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={submit} className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="expense-save">Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="expenses-table">
          <thead className="bg-stone-50 text-left">
            <tr>{["Date", "Category", "Amount", "Paid To", "Method", "Description", "Actions"].map((h) => (
              <th key={h} className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {expenses.map((e) => (
              <tr key={e.id} className="border-t border-stone-100">
                <td className="px-4 py-3">{e.date}</td>
                <td className="px-4 py-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">{e.category}</span>
                </td>
                <td className="px-4 py-3 font-medium">{fmt(e.amount)}</td>
                <td className="px-4 py-3">{e.paid_to || "—"}</td>
                <td className="px-4 py-3 text-xs">{e.payment_method}</td>
                <td className="px-4 py-3 text-stone-600 max-w-xs truncate">{e.description || "—"}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button onClick={() => edit(e)} className="p-1 hover:text-[#1B2D5C]" data-testid={`expense-edit-${e.id}`}>
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => remove(e.id)} className="p-1 hover:text-[#993333]" data-testid={`expense-delete-${e.id}`}>
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {expenses.length === 0 && (
              <tr><td colSpan="7" className="p-8 text-center text-stone-500">No expenses yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FF({ label, full, children }) {
  return (
    <div className={full ? "md:col-span-2 space-y-1.5" : "space-y-1.5"}>
      <Label className="text-xs uppercase tracking-wider text-stone-500">{label}</Label>
      {children}
    </div>
  );
}
