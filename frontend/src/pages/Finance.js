import { useEffect, useState, useCallback } from "react";
import { api, pdfUrl } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { shortInvoice } from "../lib/docNumbers";
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
  FileText, Download,
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
  const [invoices, setInvoices] = useState([]);

  const load = useCallback(async () => {
    const [s, srcs, exps, cats, invs] = await Promise.all([
      api.get("/finance/summary"),
      api.get("/funding-sources"),
      api.get("/expenses"),
      api.get("/expense-categories"),
      api.get("/invoices"),
    ]);
    setSummary(s.data);
    setSources(srcs.data);
    setExpenses(exps.data);
    setCategories(cats.data);
    setInvoices(invs.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-8" data-testid="finance-root">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-eyebrow">Treasury</div>
          <h1 className="font-display text-4xl font-semibold mt-1">Finance</h1>
        </div>
        <a
          href={pdfUrl("/finance/summary/export/pdf")}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="finance-summary-pdf-btn"
        >
          <Button className="bg-[#DC2626] hover:bg-[#B91C1C] text-white gap-2">
            <FileText className="w-4 h-4" /> {t("summary_pdf")}
          </Button>
        </a>
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

      {/* Tabs: Capital + Expenses + Invoices */}
      <Tabs defaultValue="capital" data-testid="finance-tabs">
        <TabsList
          className="bg-stone-100 border border-stone-200 p-1 rounded-lg gap-1 h-auto"
        >
          <TabsTrigger
            value="capital"
            data-testid="finance-tab-capital"
            className="data-[state=active]:bg-[#1B2D5C] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#1B2D5C] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <Landmark className="w-4 h-4 mr-2" /> {t("capital_sources")}
          </TabsTrigger>
          <TabsTrigger
            value="expenses"
            data-testid="finance-tab-expenses"
            className="data-[state=active]:bg-[#C17767] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#C17767] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <ArrowDownCircle className="w-4 h-4 mr-2" /> {t("expenses")}
          </TabsTrigger>
          <TabsTrigger
            value="invoices"
            data-testid="finance-tab-invoices"
            className="data-[state=active]:bg-[#4C7F62] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#4C7F62] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <Receipt className="w-4 h-4 mr-2" /> {t("invoices")}
          </TabsTrigger>
          <TabsTrigger
            value="calculator"
            data-testid="finance-tab-calculator"
            className="data-[state=active]:bg-[#8F9779] data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-[#8F9779] px-4 py-2 rounded-md font-medium transition-colors"
          >
            <TrendingUp className="w-4 h-4 mr-2" /> {t("loan_calculator")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="capital">
          <CapitalSection sources={sources} reload={load} t={t} />
        </TabsContent>
        <TabsContent value="expenses">
          <ExpensesSection expenses={expenses} categories={categories} reload={load} t={t} />
        </TabsContent>
        <TabsContent value="invoices">
          <InvoicesSection invoices={invoices} t={t} />
        </TabsContent>
        <TabsContent value="calculator">
          <LoanCalculatorSection t={t} />
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
  name: "", source_type: "bank", principal_amount: "", interest_rate: 5,
  interest_period: "monthly", term_months: 12,
  start_date: new Date().toISOString().slice(0, 10),
  due_date: "", notes: "",
};

const RATE_OPTIONS = [2, 3, 4, 5, 6, 7, 8, 9, 10];
const TERM_OPTIONS = [6, 7, 8, 9, 10, 11, 12];

function CapitalSection({ sources, reload, t }) {
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
      <div className="flex justify-end gap-2">
        <a
          href={pdfUrl("/finance/capital-sources/export/pdf")}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="capital-pdf-btn"
        >
          <Button variant="outline" className="gap-2 border-[#DC2626] text-[#DC2626] hover:bg-[#DC2626] hover:text-white">
            <FileText className="w-4 h-4" /> {t("export_pdf")}
          </Button>
        </a>
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
                <Select value={String(form.interest_rate)} onValueChange={(v) => setForm({ ...form, interest_rate: Number(v) })}>
                  <SelectTrigger data-testid="capital-rate"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {RATE_OPTIONS.map((r) => (
                      <SelectItem key={r} value={String(r)}>{r}%</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
              <FF label="Term (months)">
                <Select value={String(form.term_months)} onValueChange={(v) => {
                  const months = Number(v);
                  const start = form.start_date ? new Date(form.start_date) : new Date();
                  const due = new Date(start);
                  due.setMonth(due.getMonth() + months);
                  setForm({ ...form, term_months: months, due_date: due.toISOString().slice(0, 10) });
                }}>
                  <SelectTrigger data-testid="capital-term"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {TERM_OPTIONS.map((m) => (
                      <SelectItem key={m} value={String(m)}>{m} months</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FF>
              {/* Interest calculation preview */}
              <FF label="Total Interest (preview)" full>
                <div className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-sm flex items-center justify-between" data-testid="capital-interest-preview">
                  <span className="text-stone-500">
                    Principal × Rate × Term =
                  </span>
                  <span className="font-display text-lg text-[#1B2D5C]">
                    {(() => {
                      const p = Number(form.principal_amount || 0);
                      const r = Number(form.interest_rate || 0) / 100;
                      const m = Number(form.term_months || 0);
                      const factor = form.interest_period === "monthly" ? m : (form.interest_period === "yearly" ? m / 12 : 0);
                      const total = p * r * factor;
                      return fmt(total);
                    })()}
                  </span>
                </div>
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

function ExpensesSection({ expenses, categories, reload, t }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blankExpense);
  const [editingId, setEditingId] = useState(null);
  const [filterCat, setFilterCat] = useState("all");

  const filtered = filterCat === "all"
    ? expenses
    : expenses.filter((e) => e.category === filterCat);

  const pdfHref = filterCat === "all"
    ? pdfUrl("/finance/expenses/export/pdf")
    : pdfUrl(`/finance/expenses/export/pdf?category=${encodeURIComponent(filterCat)}`);

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
      <div className="flex justify-between items-center flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Label className="text-xs uppercase tracking-wider text-stone-500">
            {t("sub_category") || "Category"}
          </Label>
          <Select value={filterCat} onValueChange={setFilterCat}>
            <SelectTrigger className="w-48" data-testid="expense-filter-category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("all_categories")}</SelectItem>
              {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex gap-2">
          <a
            href={pdfHref}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="expense-pdf-btn"
          >
            <Button variant="outline" className="gap-2 border-[#DC2626] text-[#DC2626] hover:bg-[#DC2626] hover:text-white">
              <FileText className="w-4 h-4" /> {t("export_pdf")}
            </Button>
          </a>
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
      </div>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="expenses-table">
          <thead className="bg-stone-50 text-left">
            <tr>{["Date", "Category", "Amount", "Paid To", "Method", "Description", "Actions"].map((h) => (
              <th key={h} className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
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
            {filtered.length === 0 && (
              <tr><td colSpan="7" className="p-8 text-center text-stone-500">No expenses {filterCat !== "all" ? `in ${filterCat}` : "yet"}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------- Invoices (from sold auctions) ---------- */
function InvoicesSection({ invoices, t }) {
  const total = invoices.reduce((sum, i) => sum + Number(i.total || 0), 0);
  return (
    <div className="space-y-4 mt-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <div className="text-sm text-stone-600">
          <span data-testid="invoice-count">{invoices.length}</span>{" "}
          {t("invoices")} · {t("total")}: <span className="font-semibold text-[#1B2D5C]" data-testid="invoice-total-sum">{fmt(total)}</span>
        </div>
        <a
          href={pdfUrl("/invoices/export/pdf")}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="invoice-pdf-btn"
        >
          <Button variant="outline" className="gap-2 border-[#DC2626] text-[#DC2626] hover:bg-[#DC2626] hover:text-white">
            <FileText className="w-4 h-4" /> {t("export_pdf")}
          </Button>
        </a>
      </div>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="invoices-table">
          <thead className="bg-stone-50 text-left">
            <tr>{[t("invoice_number"), t("issue_date"), t("buyer"), "Contract", "Item", t("subtotal"), t("tax"), t("total"), t("status"), t("actions")].map((h, i) => (
              <th key={i} className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id} className="border-t border-stone-100" data-testid={`invoice-row-${inv.id}`}>
                <td className="px-4 py-3 font-medium" title={inv.invoice_number}>{shortInvoice(inv.invoice_number)}</td>
                <td className="px-4 py-3">{inv.date}</td>
                <td className="px-4 py-3">{inv.buyer_name || "—"}</td>
                <td className="px-4 py-3 text-stone-600">{inv.contract_number || "—"}</td>
                <td className="px-4 py-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">{inv.item_type}</span>
                </td>
                <td className="px-4 py-3">{fmt(inv.subtotal)}</td>
                <td className="px-4 py-3">{fmt(inv.tax_amount)}</td>
                <td className="px-4 py-3 font-semibold text-[#1B2D5C]">{fmt(inv.total)}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${
                    inv.status === "paid" ? "bg-emerald-50 text-emerald-800 border-emerald-200" :
                    inv.status === "cancelled" ? "bg-stone-100 text-stone-700 border-stone-200" :
                    "bg-amber-50 text-amber-800 border-amber-200"
                  }`}>{inv.status || "issued"}</span>
                </td>
                <td className="px-4 py-3">
                  <a
                    href={pdfUrl(`/invoices/${inv.id}/pdf`)}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-testid={`invoice-pdf-${inv.id}`}
                    className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-[#DC2626] text-white hover:bg-[#B91C1C]"
                  >
                    <Download className="w-3 h-3" /> PDF
                  </a>
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr><td colSpan="10" className="p-8 text-center text-stone-500">{t("no_invoices")}</td></tr>
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

/* ---------- Loan Calculator ---------- */
function LoanCalculatorSection({ t }) {
  const [principal, setPrincipal] = useState(5000);
  const [rate, setRate] = useState(5);
  const [months, setMonths] = useState(12);
  const [period, setPeriod] = useState("monthly");

  const totalInterest = (() => {
    const p = Number(principal || 0);
    const r = Number(rate || 0) / 100;
    const m = Number(months || 0);
    if (period === "monthly") return p * r * m;
    if (period === "yearly") return p * r * (m / 12);
    return 0;
  })();
  const totalRepayment = Number(principal || 0) + totalInterest;
  const monthlyPayment = months > 0 ? totalRepayment / Number(months) : 0;

  const breakdown = [];
  for (let i = 1; i <= Math.min(Number(months || 0), 12); i++) {
    const periodInterest = period === "monthly"
      ? Number(principal || 0) * (Number(rate || 0) / 100)
      : Number(principal || 0) * (Number(rate || 0) / 100) / 12;
    breakdown.push({
      month: i,
      interest: periodInterest,
      cumulativeInterest: periodInterest * i,
    });
  }

  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card className="p-6 border border-stone-200 rounded-lg shadow-none">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-[#8F9779]" />
          <h3 className="font-display text-xl font-semibold">{t("loan_calculator")}</h3>
        </div>
        <div className="space-y-4">
          <FF label="Principal (USD)">
            <Input type="number" value={principal} onChange={(e) => setPrincipal(e.target.value)} data-testid="calc-principal" />
          </FF>
          <FF label="Interest Rate %">
            <Select value={String(rate)} onValueChange={(v) => setRate(Number(v))}>
              <SelectTrigger data-testid="calc-rate"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[2, 3, 4, 5, 6, 7, 8, 9, 10].map((r) => (
                  <SelectItem key={r} value={String(r)}>{r}%</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FF>
          <FF label="Term (months)">
            <Select value={String(months)} onValueChange={(v) => setMonths(Number(v))}>
              <SelectTrigger data-testid="calc-months"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[6, 7, 8, 9, 10, 11, 12].map((m) => (
                  <SelectItem key={m} value={String(m)}>{m} months</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FF>
          <FF label="Interest Period">
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger data-testid="calc-period"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="monthly">Monthly (Rate per month)</SelectItem>
                <SelectItem value="yearly">Yearly (Rate per year)</SelectItem>
              </SelectContent>
            </Select>
          </FF>
        </div>
      </Card>

      <Card className="p-6 border border-stone-200 rounded-lg shadow-none bg-gradient-to-br from-[#1B2D5C] to-[#0F1B3A] text-white">
        <h3 className="font-display text-xl font-semibold mb-4 text-white/95">Result</h3>
        <div className="space-y-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-white/70">Total Interest</div>
            <div className="font-display text-3xl mt-1" data-testid="calc-total-interest">{fmt(totalInterest)}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs uppercase tracking-wider text-white/70">Total Repayment</div>
              <div className="font-display text-xl mt-1" data-testid="calc-total-repay">{fmt(totalRepayment)}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-white/70">Monthly Payment</div>
              <div className="font-display text-xl mt-1" data-testid="calc-monthly">{fmt(monthlyPayment)}</div>
            </div>
          </div>
          <div className="pt-3 border-t border-white/20">
            <div className="text-xs uppercase tracking-wider text-white/70 mb-2">Schedule (first {breakdown.length})</div>
            <div className="max-h-48 overflow-y-auto text-xs">
              {breakdown.map((b) => (
                <div key={b.month} className="flex justify-between py-1 border-b border-white/10">
                  <span>Month {b.month}</span>
                  <span>{fmt(b.interest)}</span>
                  <span className="text-white/70">cum {fmt(b.cumulativeInterest)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
