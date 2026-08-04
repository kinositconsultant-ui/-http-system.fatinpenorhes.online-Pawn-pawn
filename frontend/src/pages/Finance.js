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
  DialogDescription,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  SelectGroup,
  SelectLabel,
} from "../components/ui/select";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../components/ui/tabs";
import {
  Plus, Trash2, Pencil, Wallet, Landmark, Receipt, TrendingUp, ArrowDownCircle,
  FileText, Eye, BookOpen, ArrowUpCircle,
} from "lucide-react";
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Legend,
} from "recharts";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import PdfPreviewDialog from "../components/PdfPreviewDialog";

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
  const [categories, setCategories] = useState({ groups: [], flat: [] });
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
          <div className="text-eyebrow">{t("treasury")}</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">Finance</h1>
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
      <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <Kpi label={t("finance_cash_on_hand")} value={summary ? fmt(summary.cash_on_hand) : "…"}
             Icon={Wallet} tone={Number(summary?.cash_on_hand || 0) >= 0 ? "text-emerald-700" : "text-red-700"}
             testid="kpi-cash-on-hand" />
        <Kpi label={t("finance_capital_outstanding")} value={summary ? fmt(summary.capital_outstanding) : "…"}
             Icon={Landmark} tone="text-[#1B2D5C]" testid="kpi-capital-outstanding" />
        <Kpi label={t("finance_expenses_lifetime")} value={summary ? fmt(summary.expenses_total) : "…"}
             Icon={Receipt} tone="text-[#C17767]" testid="kpi-expenses-total" />
        <Kpi label={t("finance_net_profit")} value={summary ? fmt(summary.net_profit) : "…"}
             Icon={TrendingUp} tone={Number(summary?.net_profit || 0) >= 0 ? "text-emerald-700" : "text-red-700"}
             testid="kpi-net-profit" />
      </div>

      {/* Cash on Hand breakdown — shows how the balance is built up */}
      <Card className="p-4 md:p-5 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="cash-breakdown">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <div className="text-eyebrow">Cash on Hand · breakdown</div>
          {summary && !summary.opening_cash_balance && Number(summary.cash_on_hand || 0) < 0 && (
            <a
              href="/settings"
              className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300 hover:bg-amber-200"
              data-testid="opening-cash-hint"
            >
              Balance is negative — set an Opening Cash Balance in Settings
            </a>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <CashLine label="Opening cash" value={summary?.opening_cash_balance} tone="text-stone-800" />
          <CashLine label="Total inflows" value={summary?.total_inflows} tone="text-emerald-700" sign="+" />
          <CashLine label="Total outflows" value={summary?.total_outflows} tone="text-rose-700" sign="−" />
          <CashLine label="Cash on Hand" value={summary?.cash_on_hand}
                    tone={Number(summary?.cash_on_hand || 0) >= 0 ? "text-emerald-700" : "text-rose-700"} bold />
        </div>
        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-stone-500">
          <span>+ capital in: {fmt(summary?.capital_received || 0)}</span>
          <span>+ client pay: {fmt(summary?.client_payments || 0)}</span>
          <span>+ auction: {fmt(summary?.auction_sales || 0)}</span>
          <span>+ tax: {fmt(summary?.auction_tax_collected || 0)}</span>
          <span>+ inspect. reimb: {fmt(summary?.inspections_reimbursed || 0)}</span>
          <span>− loans out: {fmt(summary?.loans_disbursed || 0)}</span>
          <span>− expenses: {fmt(summary?.expenses_total || 0)}</span>
          <span>− inspections: {fmt(summary?.inspections_incurred || 0)}</span>
          <span>− cap. repaid: {fmt(summary?.capital_repaid || 0)}</span>
        </div>
      </Card>

      {/* Profit Sources — the three profit buckets requested by ownership */}
      <Card className="p-4 md:p-5 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="profit-sources">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
          <div className="text-eyebrow">Profit Sources · Fonte Lukru</div>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#1B2D5C]/10 text-[#1B2D5C] border border-[#1B2D5C]/20">
            Gross → Net breakdown
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4">
          <ProfitSourceCard
            title="Interest Received"
            subtitle="From active & redeemed contracts"
            value={fmt(summary?.interest_received || 0)}
            accent="from-sky-50 to-white border-sky-200"
            iconTone="text-sky-700"
            testid="profit-interest"
          />
          <ProfitSourceCard
            title="Penalties Received"
            subtitle="Article 8 penalty payments"
            value={fmt(summary?.total_penalty || 0)}
            accent="from-rose-50 to-white border-rose-200"
            iconTone="text-rose-700"
            testid="profit-penalty"
          />
          <ProfitSourceCard
            title="Auction Profit"
            subtitle="Sale surplus above original loan − losses"
            value={fmt(summary?.auction_net_profit ?? summary?.auction_profit ?? 0)}
            accent="from-amber-50 to-white border-amber-300"
            iconTone="text-amber-800"
            testid="profit-auction"
            detail={[
              { k: "Auction sales (cash in)", v: fmt(summary?.auction_sales || 0) },
              { k: "− Capital recovered", v: `-${fmt(summary?.auction_capital_recovered || 0)}` },
              { k: "= Realized profit", v: fmt(summary?.auction_realized_profit || 0) },
              { k: "− Realized loss", v: `-${fmt(summary?.auction_realized_loss || 0)}` },
              { k: "Interest owed at sale (info)", v: fmt(summary?.auction_interest_profit || 0) },
            ]}
          />
        </div>
        {/* Gross → Operating → Financial → Net (proper Income Statement) */}
        <div className="mt-4 rounded-md border border-stone-200 bg-stone-50 p-3 md:p-4">
          <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2 font-semibold">Income Statement · Rezultadu Netu</div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            <ProfitLine label="Gross Profit"
                       hint="Interest + Penalty + Auction"
                       value={summary?.gross_profit}
                       tone="text-[#1B2D5C]" bold />
            <ProfitLine label="Operating Expenses"
                       hint="Salary, rent, utilities…"
                       value={summary?.operating_expenses || 0}
                       tone="text-rose-700" sign="−" />
            <ProfitLine label="Operating Profit"
                       hint="Gross − Operating"
                       value={summary?.operating_profit}
                       tone={Number(summary?.operating_profit || 0) >= 0 ? "text-emerald-700" : "text-rose-700"}
                       bold />
            <ProfitLine label="Financial Expenses"
                       hint="Interest on capital"
                       value={summary?.financial_expenses || 0}
                       tone="text-amber-800" sign="−" />
            <ProfitLine label="Net Profit"
                       hint="Operating − Financial"
                       value={summary?.net_profit}
                       tone={Number(summary?.net_profit || 0) >= 0 ? "text-emerald-700" : "text-rose-700"}
                       bold />
          </div>
          <div className="mt-3 pt-3 border-t border-stone-200 flex items-center justify-between text-[11px] text-stone-500">
            <span>Margin (Net ÷ Gross)</span>
            <span className="font-medium text-stone-700 tabular-nums" data-testid="net-margin">
              {summary && summary.gross_profit
                ? `${((summary.net_profit / summary.gross_profit) * 100).toFixed(1)}%`
                : "—"}
            </span>
          </div>
        </div>
      </Card>

      {/* Cash flow + Expenses charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
        <Card className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white">
          <div className="text-eyebrow mb-3">{t("finance_cash_flow")}</div>
          <div className="h-64 md:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={[
                { k: "Opening", v: summary?.opening_cash_balance || 0 },
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
        <Card className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white">
          <div className="text-eyebrow mb-3">{t("finance_expenses_by_cat")}</div>
          <div className="h-64 md:h-72">
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
          <TabsTrigger
            value="ledger"
            data-testid="finance-tab-ledger"
            className="data-[state=active]:bg-stone-700 data-[state=active]:text-white data-[state=active]:shadow-md text-stone-600 hover:text-stone-800 px-4 py-2 rounded-md font-medium transition-colors"
          >
            <BookOpen className="w-4 h-4 mr-2" /> Ledger
          </TabsTrigger>
        </TabsList>
        <TabsContent value="capital">
          <CapitalSection sources={sources} reload={load} t={t} />
        </TabsContent>
        <TabsContent value="expenses">
          <ExpensesSection expenses={expenses} categories={categories} reload={load} t={t} />
        </TabsContent>
        <TabsContent value="invoices">
          <InvoicesSection invoices={invoices} t={t} reload={load} />
        </TabsContent>
        <TabsContent value="calculator">
          <LoanCalculatorSection t={t} />
        </TabsContent>
        <TabsContent value="ledger">
          <LedgerSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Kpi({ label, value, Icon, tone = "text-stone-900", testid }) {
  return (
    <Card className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white" data-testid={testid}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-eyebrow">{label}</div>
          <div className={`font-display text-lg md:text-3xl font-semibold mt-2 md:mt-3 break-words ${tone}`}>{value}</div>
        </div>
        <Icon className={`w-5 h-5 md:w-6 md:h-6 shrink-0 ${tone}`} />
      </div>
    </Card>
  );
}

function CashLine({ label, value, tone = "text-stone-900", sign = "", bold = false }) {
  const v = Number(value || 0);
  const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v);
  return (
    <div className="flex flex-col">
      <span className="text-[11px] uppercase tracking-wide text-stone-500">{label}</span>
      <span className={`${bold ? "font-bold text-lg" : "font-semibold"} ${tone}`}>
        {sign}{money}
      </span>
    </div>
  );
}

function ProfitSourceCard({ title, subtitle, value, accent, iconTone, detail, testid }) {
  return (
    <div
      className={`rounded-lg border bg-gradient-to-br ${accent} p-4 space-y-2`}
      data-testid={testid}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`text-xs font-medium uppercase tracking-wide ${iconTone}`}>{title}</span>
      </div>
      <div className="font-display text-2xl md:text-3xl font-semibold text-stone-900">{value}</div>
      <div className="text-[11px] text-stone-500">{subtitle}</div>
      {detail && detail.length > 0 && (
        <div className="mt-2 pt-2 border-t border-stone-200/70 space-y-0.5">
          {detail.map((d) => (
            <div key={d.k} className="flex items-center justify-between text-[11px] text-stone-600">
              <span>{d.k}</span>
              <span className="font-medium tabular-nums">{d.v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfitLine({ label, hint, value, raw, tone = "text-stone-900", sign = "", bold = false }) {
  const isRaw = raw !== undefined && raw !== null;
  const money = isRaw
    ? raw
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value || 0));
  return (
    <div className="flex flex-col">
      <span className="text-[11px] uppercase tracking-wide text-stone-500">{label}</span>
      <span className={`${bold ? "font-bold text-lg" : "font-semibold"} ${tone}`}>
        {isRaw ? money : `${sign}${money}`}
      </span>
      <span className="text-[10px] text-stone-500 leading-tight">{hint}</span>
    </div>
  );
}

/* ---------- Capital Sources ---------- */
const blankSource = {
  name: "", source_type: "bank", principal_amount: "", interest_rate: 5,
  interest_period: "monthly", term_months: 12,
  payment_frequency: "monthly",
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
  const [repForm, setRepForm] = useState({ principal_amount: "", interest_amount: "", date: new Date().toISOString().slice(0, 10), notes: "" });
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyFor, setHistoryFor] = useState(null);
  const [historyRows, setHistoryRows] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTab, setHistoryTab] = useState("payments"); // "payments" | "schedule"
  const [scheduleRows, setScheduleRows] = useState([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const openHistory = async (source) => {
    setHistoryFor(source);
    setHistoryOpen(true);
    setHistoryTab("payments");
    setHistoryLoading(true);
    setScheduleRows([]);
    try {
      const r = await api.get(`/funding-sources/${source.id}/repayments`);
      setHistoryRows(r.data || []);
    } catch (e) {
      toast.error("Failed to load history");
    } finally {
      setHistoryLoading(false);
    }
  };
  const loadSchedule = async () => {
    if (!historyFor || scheduleRows.length > 0) return;
    setScheduleLoading(true);
    try {
      const r = await api.get(`/funding-sources/${historyFor.id}/schedule`);
      setScheduleRows(r.data?.rows || []);
    } catch (e) {
      toast.error("Failed to load schedule");
    } finally {
      setScheduleLoading(false);
    }
  };
  const deleteRepayment = async (rid) => {
    if (!window.confirm("Delete this repayment? Capital Outstanding + Net Profit will be restored. This action is logged.")) return;
    try {
      await api.delete(`/funding-sources/${historyFor.id}/repayments/${rid}`);
      toast.success("Repayment reversed");
      // Refresh drawer + parent list
      const r = await api.get(`/funding-sources/${historyFor.id}/repayments`);
      setHistoryRows(r.data || []);
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

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
      const principal = Number(repForm.principal_amount || 0);
      const interest = Number(repForm.interest_amount || 0);
      if (principal <= 0 && interest <= 0) {
        toast.error("Enter a principal or interest amount");
        return;
      }
      await api.post(`/funding-sources/${repFor.id}/repayments`, {
        source_id: repFor.id,
        principal_amount: principal,
        interest_amount: interest,
        date: repForm.date,
        notes: repForm.notes,
      });
      toast.success("Repayment recorded — interest booked as expense");
      setRepOpen(false); setRepForm({ principal_amount: "", interest_amount: "", date: new Date().toISOString().slice(0, 10), notes: "" });
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
              <FF label="Payment Frequency">
                <Select value={form.payment_frequency} onValueChange={(v) => setForm({ ...form, payment_frequency: v })}>
                  <SelectTrigger data-testid="capital-frequency"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">Monthly · fulan-fulan</SelectItem>
                    <SelectItem value="quarterly">Quarterly · trimestrál</SelectItem>
                    <SelectItem value="lump_sum">Lump sum · pagamentu ida deit</SelectItem>
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
            <tr>{["Name", "Type", "Initial Loan", "Principal Paid", "Principal Left", "Interest Paid", "Interest Left", "Next Due", "Status", "Actions"].map((h) => (
              <th key={h} className="px-3 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold">{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {sources.map((s) => {
              const statusStyles = {
                on_time: "bg-emerald-50 text-emerald-700 border-emerald-200",
                due_soon: "bg-amber-50 text-amber-800 border-amber-300",
                overdue: "bg-rose-50 text-rose-700 border-rose-300",
                closed: "bg-stone-100 text-stone-500 border-stone-200",
              };
              const statusLabels = {
                on_time: "On Time",
                due_soon: "Due Soon",
                overdue: "Overdue",
                closed: "Closed",
              };
              const st = s.status || "on_time";
              return (
              <tr key={s.id} className="border-t border-stone-100" data-testid={`capital-row-${s.id}`}>
                <td className="px-3 py-3 font-medium">
                  {s.name}
                  <div className="text-[10px] text-stone-500 mt-0.5">
                    {s.interest_rate}% / {s.interest_period} · {s.term_months || "—"} mo
                    {s.payment_frequency && s.payment_frequency !== "monthly" && (
                      <> · {s.payment_frequency === "quarterly" ? "Quarterly" : "Lump sum"}</>
                    )}
                  </div>
                </td>
                <td className="px-3 py-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">{s.source_type}</span>
                </td>
                <td className="px-3 py-3">{fmt(s.principal_amount)}</td>
                <td className="px-3 py-3 text-emerald-700">{fmt(s.principal_paid)}</td>
                <td className="px-3 py-3 font-medium text-[#C17767]" data-testid={`capital-principal-left-${s.id}`}>{fmt(s.principal_remaining)}</td>
                <td className="px-3 py-3 text-emerald-700">{fmt(s.interest_paid)}</td>
                <td className="px-3 py-3">{fmt(s.interest_remaining)}</td>
                <td className="px-3 py-3">{s.next_due_date || "—"}</td>
                <td className="px-3 py-3">
                  <span
                    className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${statusStyles[st]}`}
                    data-testid={`capital-status-${s.id}`}
                    title={s.days_until_due !== null ? `${s.days_until_due} days until next due` : ""}
                  >
                    {statusLabels[st]}
                  </span>
                </td>
                <td className="px-3 py-3">
                  <div className="flex gap-2">
                    <button onClick={() => { setRepFor(s); setRepOpen(true); }} data-testid={`capital-repay-${s.id}`}
                            className="text-xs px-2 py-1 rounded-md bg-[#1B2D5C] text-white hover:bg-[#0F1B3A]">Repay</button>
                    <button onClick={() => openHistory(s)} data-testid={`capital-history-${s.id}`}
                            className="text-xs px-2 py-1 rounded-md bg-stone-100 border border-stone-300 text-stone-700 hover:bg-stone-200">History</button>
                    <a href={pdfUrl(`/funding-sources/${s.id}/amortization-pdf`)} target="_blank" rel="noreferrer"
                       data-testid={`capital-schedule-${s.id}`}
                       className="text-xs px-2 py-1 rounded-md bg-amber-50 border border-amber-300 text-amber-900 hover:bg-amber-100">Schedule</a>
                    <button onClick={() => edit(s)} className="p-1 hover:text-[#1B2D5C]" data-testid={`capital-edit-${s.id}`}>
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => remove(s.id)} className="p-1 hover:text-[#993333]" data-testid={`capital-delete-${s.id}`}>
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
              );
            })}
            {sources.length === 0 && (
              <tr><td colSpan="10" className="p-8 text-center text-stone-500">No capital sources yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Repayment History — {historyFor?.name}</DialogTitle>
            <DialogDescription className="sr-only">Full audit trail of every repayment made against this capital source.</DialogDescription>
          </DialogHeader>
          {historyFor && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs mb-3 rounded-md bg-stone-50 border border-stone-200 px-3 py-2">
              <div><span className="text-stone-500">Principal Paid</span><br /><b className="text-emerald-700">{fmt(historyFor.principal_paid)}</b></div>
              <div><span className="text-stone-500">Principal Left</span><br /><b className="text-[#C17767]">{fmt(historyFor.principal_remaining)}</b></div>
              <div><span className="text-stone-500">Interest Paid</span><br /><b className="text-emerald-700">{fmt(historyFor.interest_paid)}</b></div>
              <div><span className="text-stone-500">Interest Left</span><br /><b>{fmt(historyFor.interest_remaining)}</b></div>
            </div>
          )}
          {/* Tab switcher */}
          <div className="flex gap-1 mb-3 border-b border-stone-200">
            {[
              { k: "payments", label: "Payments" },
              { k: "schedule", label: "Schedule" },
            ].map((t) => (
              <button
                key={t.k}
                onClick={() => {
                  setHistoryTab(t.k);
                  if (t.k === "schedule") loadSchedule();
                }}
                data-testid={`history-tab-${t.k}`}
                className={`px-3 py-1.5 text-xs font-medium border-b-2 -mb-px ${
                  historyTab === t.k
                    ? "border-[#1B2D5C] text-[#1B2D5C]"
                    : "border-transparent text-stone-500 hover:text-stone-800"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {historyTab === "payments" && (
          <div className="overflow-x-auto max-h-[50vh]">
            <table className="min-w-full text-sm" data-testid="history-table">
              <thead className="bg-stone-50 sticky top-0">
                <tr>{["Date", "Principal", "Interest", "Total", "Notes", isAdmin ? "" : null].filter(Boolean).map((h) => (
                  <th key={h} className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold text-left">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {historyLoading && (
                  <tr><td colSpan={isAdmin ? 6 : 5} className="text-center py-6 text-stone-400">Loading…</td></tr>
                )}
                {!historyLoading && historyRows.length === 0 && (
                  <tr><td colSpan={isAdmin ? 6 : 5} className="text-center py-6 text-stone-400">No repayments recorded yet.</td></tr>
                )}
                {!historyLoading && historyRows.map((r) => (
                  <tr key={r.id} className="border-t border-stone-100" data-testid={`history-row-${r.id}`}>
                    <td className="px-3 py-2 whitespace-nowrap tabular-nums">{r.date}</td>
                    <td className="px-3 py-2 tabular-nums text-emerald-700">{fmt(r.principal_amount)}</td>
                    <td className="px-3 py-2 tabular-nums text-amber-800">{fmt(r.interest_amount)}</td>
                    <td className="px-3 py-2 tabular-nums font-medium">{fmt(r.amount)}</td>
                    <td className="px-3 py-2 text-stone-600 max-w-[240px] truncate" title={r.notes}>{r.notes || "—"}</td>
                    {isAdmin && (
                      <td className="px-3 py-2">
                        <button
                          onClick={() => deleteRepayment(r.id)}
                          data-testid={`history-delete-${r.id}`}
                          className="text-rose-700 hover:text-rose-900 p-1"
                          title="Reverse this repayment"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
          {historyTab === "schedule" && (
          <div className="overflow-x-auto max-h-[50vh]">
            <table className="min-w-full text-sm" data-testid="schedule-table">
              <thead className="bg-stone-50 sticky top-0">
                <tr>{["#", "Due Date", "Opening", "Principal", "Interest", "Payment", "Ending", "Status"].map((h) => (
                  <th key={h} className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold text-left">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {scheduleLoading && (
                  <tr><td colSpan="8" className="text-center py-6 text-stone-400">Loading…</td></tr>
                )}
                {!scheduleLoading && scheduleRows.length === 0 && (
                  <tr><td colSpan="8" className="text-center py-6 text-stone-400">No schedule available.</td></tr>
                )}
                {!scheduleLoading && scheduleRows.map((r) => {
                  const styles = {
                    paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
                    due_soon: "bg-amber-50 text-amber-800 border-amber-300",
                    overdue: "bg-rose-50 text-rose-700 border-rose-300",
                    scheduled: "bg-stone-100 text-stone-600 border-stone-200",
                  };
                  const labels = { paid: "Paid", due_soon: "Due Soon", overdue: "Overdue", scheduled: "Scheduled" };
                  return (
                    <tr key={r.installment} className="border-t border-stone-100" data-testid={`schedule-row-${r.installment}`}>
                      <td className="px-3 py-2 tabular-nums text-stone-500">{r.installment}</td>
                      <td className="px-3 py-2 tabular-nums">{r.due_date}</td>
                      <td className="px-3 py-2 tabular-nums text-stone-500">{fmt(r.opening_balance)}</td>
                      <td className="px-3 py-2 tabular-nums text-emerald-700">{fmt(r.principal)}</td>
                      <td className="px-3 py-2 tabular-nums text-amber-800">{fmt(r.interest)}</td>
                      <td className="px-3 py-2 tabular-nums font-medium">{fmt(r.payment)}</td>
                      <td className="px-3 py-2 tabular-nums text-stone-600">{fmt(r.ending_balance)}</td>
                      <td className="px-3 py-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${styles[r.status]}`}>
                          {labels[r.status]}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setHistoryOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={repOpen} onOpenChange={setRepOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record Repayment — {repFor?.name}</DialogTitle>
            <DialogDescription className="sr-only">Record a capital repayment split into principal (reduces debt) and interest (booked as an expense).</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {repFor && (
              <div className="rounded-md bg-stone-50 border border-stone-200 px-3 py-2 text-xs text-stone-600 grid grid-cols-2 gap-2">
                <div><span className="text-stone-400">Principal Left</span><br /><span className="font-display text-[#C17767]" data-testid="rep-dialog-p-left">{fmt(repFor.principal_remaining)}</span></div>
                <div><span className="text-stone-400">Interest Remaining</span><br /><span className="font-display text-stone-700">{fmt(repFor.interest_remaining)}</span></div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <FF label="Principal Payment">
                <Input type="number" step="0.01" min="0"
                       value={repForm.principal_amount}
                       onChange={(e) => setRepForm({ ...repForm, principal_amount: e.target.value })}
                       data-testid="capital-rep-principal"
                       placeholder="Reduces debt" />
              </FF>
              <FF label="Interest Payment">
                <Input type="number" step="0.01" min="0"
                       value={repForm.interest_amount}
                       onChange={(e) => setRepForm({ ...repForm, interest_amount: e.target.value })}
                       data-testid="capital-rep-interest"
                       placeholder="Booked as expense" />
              </FF>
            </div>
            <div className="rounded-md bg-indigo-50 border border-indigo-200 px-3 py-2 text-xs text-indigo-900 flex items-center justify-between">
              <span>Total Cash Out</span>
              <span className="font-display text-base" data-testid="capital-rep-total">
                {fmt(Number(repForm.principal_amount || 0) + Number(repForm.interest_amount || 0))}
              </span>
            </div>
            <p className="text-[11px] text-stone-500 leading-relaxed">
              Interest paid is automatically booked as an expense under <b>Interest Expense (Capital)</b> and will reduce Net Profit. Principal reduces the outstanding balance and Cash on Hand.
            </p>
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
              {(categories.groups || []).map((g) => (
                <SelectGroup key={g.label}>
                  <SelectLabel className="text-[10px] uppercase tracking-wider text-stone-500 pt-2">{g.label}</SelectLabel>
                  {g.items.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectGroup>
              ))}
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
                  <SelectTrigger data-testid="expense-category"><SelectValue placeholder="Select a category" /></SelectTrigger>
                  <SelectContent className="max-h-80">
                    {(categories.groups || []).map((g) => (
                      <SelectGroup key={g.label}>
                        <SelectLabel className="text-[10px] uppercase tracking-wider text-stone-500 pt-2">{g.label}</SelectLabel>
                        {g.items.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                      </SelectGroup>
                    ))}
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
function InvoicesSection({ invoices, t, reload }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const total = invoices.reduce((sum, i) => sum + Number(i.total || 0), 0);
  const [preview, setPreview] = useState({ open: false, url: "", title: "", filename: "" });

  const openPreview = (inv) => {
    setPreview({
      open: true,
      url: pdfUrl(`/invoices/${inv.id}/pdf`),
      title: `${t("invoice")} ${shortInvoice(inv.invoice_number) || inv.invoice_number}`,
      filename: `${inv.invoice_number || "invoice"}.pdf`,
    });
  };
  const openListPreview = () => {
    setPreview({
      open: true,
      url: pdfUrl("/invoices/export/pdf"),
      title: t("invoices"),
      filename: "invoices.pdf",
    });
  };
  const remove = async (inv) => {
    const label = inv.invoice_number || inv.id;
    if (!window.confirm(
      `Delete invoice ${label}?\nThis removes the invoice record permanently. The linked auction (if any) will keep its sold status but lose its invoice link.`
    )) return;
    try {
      await api.delete(`/invoices/${inv.id}`);
      toast.success("Invoice deleted");
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-4 mt-4">
      <div className="flex justify-between items-center flex-wrap gap-2">
        <div className="text-sm text-stone-600">
          <span data-testid="invoice-count">{invoices.length}</span>{" "}
          {t("invoices")} · {t("total")}: <span className="font-semibold text-[#1B2D5C]" data-testid="invoice-total-sum">{fmt(total)}</span>
        </div>
        <Button
          type="button"
          onClick={openListPreview}
          variant="outline"
          className="gap-2 border-[#DC2626] text-[#DC2626] hover:bg-[#DC2626] hover:text-white"
          data-testid="invoice-pdf-btn"
        >
          <FileText className="w-4 h-4" /> {t("export_pdf")}
        </Button>
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
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => openPreview(inv)}
                      data-testid={`invoice-pdf-${inv.id}`}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-[#DC2626] text-white hover:bg-[#B91C1C]"
                      title={t("preview")}
                    >
                      <Eye className="w-3 h-3" /> PDF
                    </button>
                    {isAdmin && (
                      <button
                        type="button"
                        onClick={() => remove(inv)}
                        data-testid={`invoice-delete-${inv.id}`}
                        className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-white border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors"
                        title="Delete invoice (admin only)"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr><td colSpan="10" className="p-8 text-center text-stone-500">{t("no_invoices")}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <PdfPreviewDialog
        open={preview.open}
        onOpenChange={(o) => setPreview((p) => ({ ...p, open: o }))}
        url={preview.url}
        title={preview.title}
        downloadName={preview.filename}
      />
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

// -------------------------------------------------------------
// Ledger tab — filterable, sortable table of every cash movement
// -------------------------------------------------------------
function LedgerSection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(90);
  const [kindFilter, setKindFilter] = useState("all");
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState("date");
  const [sortDir, setSortDir] = useState("desc");

  const load = async (d = days) => {
    setLoading(true);
    try {
      const r = await api.get(`/finance/cash-ledger?days=${d}`);
      setData(r.data);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const rows = (data?.entries || []).filter((e) => {
    if (kindFilter !== "all" && e.kind !== kindFilter) return false;
    if (q.trim()) {
      const s = `${e.reference} ${e.notes}`.toLowerCase();
      if (!s.includes(q.toLowerCase())) return false;
    }
    return true;
  });
  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av === bv) return 0;
    const cmp = typeof av === "number" ? av - bv : String(av).localeCompare(String(bv));
    return sortDir === "asc" ? cmp : -cmp;
  });
  const toggleSort = (k) => {
    if (sortKey === k) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(k); setSortDir("desc"); }
  };
  const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(Number(n || 0));

  const kinds = [
    "all", "disbursement", "payment", "expense", "inspection_out", "inspection_reimb",
    "capital_in", "capital_out", "auction_sale", "auction_tax",
  ];
  const kindColor = {
    disbursement: "bg-rose-100 text-rose-800 border-rose-300",
    payment: "bg-emerald-100 text-emerald-800 border-emerald-300",
    expense: "bg-rose-100 text-rose-800 border-rose-300",
    inspection_out: "bg-amber-100 text-amber-800 border-amber-300",
    inspection_reimb: "bg-emerald-100 text-emerald-800 border-emerald-300",
    capital_in: "bg-sky-100 text-sky-800 border-sky-300",
    capital_out: "bg-rose-100 text-rose-800 border-rose-300",
    auction_sale: "bg-amber-100 text-amber-800 border-amber-300",
    auction_tax: "bg-stone-100 text-stone-700 border-stone-300",
  };

  return (
    <div className="space-y-3" data-testid="ledger-section">
      {/* Header + filters */}
      <Card className="p-3 md:p-4 border border-stone-200 shadow-none rounded-lg bg-white flex flex-wrap items-end gap-3">
        <div>
          <label className="text-xs uppercase tracking-wider text-stone-500 block">Period (days)</label>
          <select
            value={days}
            onChange={(e) => { const d = Number(e.target.value); setDays(d); load(d); }}
            className="mt-1 border border-stone-300 rounded-md px-2 py-1.5 text-sm"
            data-testid="ledger-days"
          >
            {[7, 30, 60, 90, 180, 365].map((d) => (
              <option key={d} value={d}>{d} days</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-wider text-stone-500 block">Kind</label>
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            className="mt-1 border border-stone-300 rounded-md px-2 py-1.5 text-sm"
            data-testid="ledger-kind"
          >
            {kinds.map((k) => (<option key={k} value={k}>{k}</option>))}
          </select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs uppercase tracking-wider text-stone-500 block">Search reference / notes</label>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="mt-1 w-full border border-stone-300 rounded-md px-2 py-1.5 text-sm"
            placeholder="receipt no · contract no · description…"
            data-testid="ledger-search"
          />
        </div>
        {data && (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide text-stone-500">Balance</div>
            <div className={`font-display text-xl font-semibold ${Number(data.closing_balance) >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
              {money(data.closing_balance)}
            </div>
            <div className="text-[10px] text-stone-500">
              Opening {money(data.opening_cash)} · +{money(data.total_in)} · −{money(data.total_out)}
            </div>
          </div>
        )}
      </Card>

      {/* Table */}
      <Card className="p-0 border border-stone-200 shadow-none rounded-lg bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="ledger-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <LedTh sortKey="date" cur={sortKey} dir={sortDir} onClick={toggleSort}>Date</LedTh>
              <LedTh sortKey="kind" cur={sortKey} dir={sortDir} onClick={toggleSort}>Kind</LedTh>
              <LedTh>Reference</LedTh>
              <LedTh>Notes</LedTh>
              <LedTh sortKey="amount" cur={sortKey} dir={sortDir} onClick={toggleSort} right>Amount</LedTh>
              <LedTh right>Running Balance</LedTh>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} className="text-center py-6 text-stone-400">Loading…</td></tr>
            )}
            {!loading && sorted.length === 0 && (
              <tr><td colSpan={6} className="text-center py-6 text-stone-400">No entries in this window.</td></tr>
            )}
            {!loading && sorted.map((e, i) => (
              <tr key={i} className="border-t border-stone-100 hover:bg-stone-50/60" data-testid={`ledger-row-${i}`}>
                <td className="px-3 py-1.5 whitespace-nowrap tabular-nums">{e.date}</td>
                <td className="px-3 py-1.5">
                  <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border text-[10px] ${kindColor[e.kind] || "bg-stone-100 text-stone-700 border-stone-200"}`}>
                    {e.amount >= 0
                      ? <ArrowUpCircle className="w-3 h-3" />
                      : <ArrowDownCircle className="w-3 h-3" />}
                    {e.kind}
                  </span>
                </td>
                <td className="px-3 py-1.5 font-mono text-xs text-stone-600">{e.reference || "—"}</td>
                <td className="px-3 py-1.5 max-w-[360px] truncate" title={e.notes}>{e.notes}</td>
                <td className={`px-3 py-1.5 text-right font-semibold tabular-nums ${e.amount >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                  {e.amount >= 0 ? "+" : ""}{money(e.amount)}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums">{money(e.running_balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function LedTh({ children, sortKey: sk, cur, dir, onClick, right }) {
  const active = sk && cur === sk;
  return (
    <th
      onClick={() => sk && onClick && onClick(sk)}
      className={`px-3 py-2 text-[10px] uppercase tracking-wider font-semibold whitespace-nowrap select-none ${
        sk ? "cursor-pointer hover:text-[#1B2D5C]" : ""
      } ${active ? "text-[#1B2D5C]" : "text-stone-500"} ${right ? "text-right" : ""}`}
    >
      {children}
      {active && <span className="ml-1">{dir === "asc" ? "▲" : "▼"}</span>}
    </th>
  );
}

