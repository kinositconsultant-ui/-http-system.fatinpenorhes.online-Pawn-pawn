import { useEffect, useMemo, useState, useCallback } from "react";
import { api, API_BASE } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  FileText,
  FileDown,
  Printer,
  RefreshCw,
  FileSpreadsheet,
  Filter as FilterIcon,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
} from "lucide-react";
import MonthEndBundle from "../components/MonthEndBundle";

// 6 report tabs from user spec — each with a distinct accent color
const TABS = [
  { key: "active-contracts", labelKey: "active_contract",
    color: "#1B2D5C", soft: "bg-[#1B2D5C]/10 text-[#1B2D5C]",
    kpis: ["total_contracts", "total_loan", "tax_accumulate", "almost_expired"] },
  { key: "payments", labelKey: "payments",
    color: "#4C7F62", soft: "bg-[#4C7F62]/10 text-[#4C7F62]",
    kpis: ["total_transactions", "total_payments", "interest_received", "total_penalty"] },
  { key: "overdue", labelKey: "total_overdue",
    color: "#C17767", soft: "bg-[#C17767]/10 text-[#C17767]",
    kpis: ["total_overdue", "total_outstanding", "total_interest", "near_expired"] },
  { key: "auction", labelKey: "auctions",
    color: "#B45309", soft: "bg-amber-100 text-amber-800",
    kpis: ["total_auction", "total_amount"] },
  { key: "inventory", labelKey: "inventory",
    color: "#7C3AED", soft: "bg-violet-100 text-violet-800",
    kpis: ["total_items", "total_amount", "active_items", "overdue_items"] },
  { key: "financial", labelKey: "financial",
    color: "#0F766E", soft: "bg-teal-100 text-teal-800",
    kpis: ["total_loan", "total_payment", "interest_received", "profit"] },
  { key: "treasury", labelKey: "finance",
    color: "#8F9779", soft: "bg-[#8F9779]/15 text-[#5C6753]",
    kpis: ["capital_received", "capital_outstanding", "expenses_total", "expense_categories"] },
];

const MONEY_KEYS = new Set([
  "total_loan", "total_loan_amount", "tax_accumulate", "total_payments",
  "interest_received", "total_penalty", "total_outstanding", "total_interest",
  "total_amount", "total_payment", "profit", "loan_amount", "amount",
  "principal_remaining", "interest_remaining", "penalty", "market_value",
  "paid_amount", "starting_price", "sold_price", "interest_amount",
]);

const fmtMoney = (v) => {
  const n = Number(v ?? 0);
  return `$${n.toLocaleString("en-US", {
    minimumFractionDigits: 0, maximumFractionDigits: 2,
  })}`;
};

const fmtCell = (col, v) => {
  if (v == null || v === "") return "—";
  if (MONEY_KEYS.has(col)) return fmtMoney(v);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
};

const MONTHS_EN = [
  ["1", "January"], ["2", "February"], ["3", "March"], ["4", "April"],
  ["5", "May"], ["6", "June"], ["7", "July"], ["8", "August"],
  ["9", "September"], ["10", "October"], ["11", "November"], ["12", "December"],
];

// Columns that should never wrap (dates, money, IDs stay on one line).
const NO_WRAP_KEYS = new Set([
  ...MONEY_KEYS,
  "date", "due_date", "contract_date", "sold_at", "created_at", "start_date",
  "contract_number", "receipt_number", "id", "interest_rate", "status",
  "type", "kind", "item_type", "payment_method",
]);
// Wide text columns → allow wrapping and cap width so tables stay readable.
const WIDE_KEYS = new Set([
  "item", "description", "notes", "buyer_name", "paid_to",
  "item_brand", "item_model", "brand", "model",
]);

const cellClass = (col) => {
  const base = "px-2.5 py-2 align-top";
  if (WIDE_KEYS.has(col)) return `${base} whitespace-normal break-words max-w-[220px]`;
  if (NO_WRAP_KEYS.has(col)) return `${base} whitespace-nowrap`;
  return `${base} whitespace-nowrap`;
};

export default function Reports() {
  const { t } = useLang();
  const [tab, setTab] = useState("active-contracts");
  const [filters, setFilters] = useState({ month: "", year: "", category: "", sub_category: "" });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  // Client-side sort: null = server order, otherwise { key, dir: "asc" | "desc" }
  const [sort, setSort] = useState(null);

  const yearOpts = useMemo(() => {
    const now = new Date().getFullYear();
    return [String(now - 1), String(now), String(now + 1)];
  }, []);

  const buildQuery = useCallback(() => {
    const p = new URLSearchParams();
    if (filters.month) p.set("month", filters.month);
    if (filters.year) p.set("year", filters.year);
    if (filters.category) p.set("category", filters.category);
    if (filters.sub_category) p.set("sub_category", filters.sub_category);
    return p.toString();
  }, [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = buildQuery();
      const { data: d } = await api.get(`/reports/v2/${tab}${q ? `?${q}` : ""}`);
      setData(d);
    } catch (e) {
      setData(null);
    }
    setLoading(false);
  }, [tab, buildQuery]);

  useEffect(() => { load(); }, [load]);
  // Reset any active sort whenever the active tab changes (columns differ per tab)
  useEffect(() => { setSort(null); }, [tab]);

  const sortedRows = useMemo(() => {
    const rows = data?.rows || [];
    if (!sort) return rows;
    const { key, dir } = sort;
    const mul = dir === "asc" ? 1 : -1;
    const isNumericKey = MONEY_KEYS.has(key)
      || ["interest_rate", "manufacture_year", "total_repaid", "outstanding"].includes(key);
    const isDateKey = ["date", "due_date", "contract_date", "sold_at", "created_at", "start_date"].includes(key);

    const val = (r) => {
      const v = r?.[key];
      if (v == null || v === "") return null;
      if (isNumericKey) {
        const n = typeof v === "number" ? v : parseFloat(String(v).replace(/[^0-9.\-]/g, ""));
        return Number.isNaN(n) ? null : n;
      }
      if (isDateKey) {
        const t = Date.parse(v);
        return Number.isNaN(t) ? null : t;
      }
      return String(v).toLowerCase();
    };

    // Stable sort with nulls last
    return rows
      .map((r, i) => ({ r, i }))
      .sort((a, b) => {
        const va = val(a.r);
        const vb = val(b.r);
        if (va == null && vb == null) return a.i - b.i;
        if (va == null) return 1;
        if (vb == null) return -1;
        if (va < vb) return -1 * mul;
        if (va > vb) return 1 * mul;
        return a.i - b.i;
      })
      .map((x) => x.r);
  }, [data, sort]);

  const toggleSort = (key) => {
    setSort((cur) => {
      if (!cur || cur.key !== key) return { key, dir: "asc" };
      if (cur.dir === "asc") return { key, dir: "desc" };
      return null; // third click → clear
    });
  };

  const resetFilters = () => setFilters({ month: "", year: "", category: "", sub_category: "" });

  const exportUrl = (format) => {
    const q = buildQuery();
    return `${API_BASE}/reports/v2/${tab}/export?format=${format}${q ? `&${q}` : ""}`;
  };
  const printPage = () => window.print();

  const currentTab = TABS.find((t) => t.key === tab);

  return (
    <div className="space-y-6 print:space-y-3" data-testid="reports-root">
      <header className="print:hidden">
        <div className="text-eyebrow">{t("reports")}</div>
        <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
          {t(currentTab?.labelKey || "reports")}
        </h1>
      </header>

      {/* Tab navigation — color-coded per category */}
      <div className="flex flex-wrap gap-2 print:hidden" data-testid="report-tabs">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            data-testid={`report-tab-${tb.key}`}
            style={tab === tb.key ? { backgroundColor: tb.color, color: "white" } : undefined}
            className={`px-4 py-2.5 text-sm font-medium tracking-wide rounded-md transition shadow-sm ${
              tab === tb.key
                ? "shadow-md"
                : `${tb.soft} hover:opacity-90`
            }`}
          >
            {t(tb.labelKey)}
          </button>
        ))}
      </div>

      {/* Filter bar */}
      <Card className="p-4 border border-stone-200 shadow-none rounded-lg bg-stone-50 print:hidden">
        <div className="flex flex-wrap gap-3 items-end">
          <FilterField label={t("month")}>
            <Select
              value={filters.month || "all"}
              onValueChange={(v) => setFilters((f) => ({ ...f, month: v === "all" ? "" : v }))}
            >
              <SelectTrigger className="w-40" data-testid="filter-month">
                <SelectValue placeholder={t("month")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("month")} —</SelectItem>
                {MONTHS_EN.map(([v, label]) => (
                  <SelectItem key={v} value={v}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("year")}>
            <Select
              value={filters.year || "all"}
              onValueChange={(v) => setFilters((f) => ({ ...f, year: v === "all" ? "" : v }))}
            >
              <SelectTrigger className="w-32" data-testid="filter-year">
                <SelectValue placeholder={t("year")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("year")} —</SelectItem>
                {yearOpts.map((y) => (
                  <SelectItem key={y} value={y}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("category")}>
            <Select
              value={filters.category || "all"}
              onValueChange={(v) => setFilters((f) => ({ ...f, category: v === "all" ? "" : v, sub_category: "" }))}
            >
              <SelectTrigger className="w-44" data-testid="filter-category">
                <SelectValue placeholder={t("category")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="car">{t("car")}</SelectItem>
                <SelectItem value="motorcycle">{t("motorcycle")}</SelectItem>
                <SelectItem value="electronic">{t("electronic")}</SelectItem>
                <SelectItem value="pezadu">{t("pezadu")}</SelectItem>
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label={t("sub_category")}>
            <Input
              placeholder={t("sub_category")}
              value={filters.sub_category}
              onChange={(e) => setFilters((f) => ({ ...f, sub_category: e.target.value }))}
              className="w-44"
              data-testid="filter-sub-category"
            />
          </FilterField>

          <div className="flex gap-2 ml-auto" data-testid="report-actions">
            <Button onClick={load} className="bg-[#1B2D5C] hover:bg-[#0F1B3A]" data-testid="filter-apply">
              <FilterIcon className="w-4 h-4 mr-1" /> {t("filter")}
            </Button>
            <Button variant="outline" onClick={resetFilters} data-testid="filter-reset">
              <RefreshCw className="w-4 h-4 mr-1" /> {t("reset")}
            </Button>
            <Button variant="outline" onClick={printPage} data-testid="report-print">
              <Printer className="w-4 h-4 mr-1" /> {t("print")}
            </Button>
            <a
              href={exportUrl("pdf")}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-3 py-2 rounded-md text-sm border border-red-200 bg-red-50 text-red-700 hover:bg-red-600 hover:text-white hover:border-red-600 transition"
              data-testid="report-pdf"
            >
              <FileText className="w-4 h-4" /> {t("pdf")}
            </a>
            <a
              href={exportUrl("xlsx")}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-3 py-2 rounded-md text-sm border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-600 hover:text-white hover:border-emerald-600 transition"
              data-testid="report-excel"
            >
              <FileSpreadsheet className="w-4 h-4" /> {t("excel")}
            </a>
          </div>
        </div>
      </Card>

      {/* KPI cards */}
      <div className={`grid gap-3 md:gap-4 ${currentTab.kpis.length === 2 ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-2 md:grid-cols-2 lg:grid-cols-4"}`}>
        {currentTab.kpis.map((k) => {
          const v = data?.kpis?.[k];
          return (
            <Card
              key={k}
              className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white"
              data-testid={`kpi-${k}`}
            >
              <div className="text-eyebrow">{t(k) === k ? prettify(k) : t(k)}</div>
              <div className="font-display text-xl md:text-3xl font-semibold mt-2 md:mt-3 text-stone-900 break-words">
                {data == null ? "…" : MONEY_KEYS.has(k) ? fmtMoney(v) : v ?? "—"}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Detail table */}
      <Card className="border border-stone-200 shadow-none rounded-lg bg-white overflow-hidden">
        <div className="px-4 md:px-6 pt-4 md:pt-5 pb-3 border-b border-stone-200">
          <div className="text-eyebrow">{t("detail")}</div>
          <div className="font-display text-lg mt-1 text-stone-900">
            {t(currentTab.labelKey)} · {sortedRows.length} rows
            {sort && (
              <button
                onClick={() => setSort(null)}
                className="ml-3 text-xs font-normal text-stone-500 hover:text-[#1B2D5C] underline underline-offset-2"
                data-testid="report-sort-clear"
              >
                sorted by {prettify(sort.key)} ({sort.dir}) · clear
              </button>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs" data-testid="report-table">
            <thead className="bg-stone-50 text-left">
              <tr>
                {(data?.columns || []).map((c) => {
                  const active = sort?.key === c;
                  const Icon = active ? (sort.dir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
                  return (
                    <th
                      key={c}
                      onClick={() => toggleSort(c)}
                      data-testid={`report-th-${c}`}
                      className={`px-2.5 py-2.5 text-[10px] uppercase tracking-wider font-semibold whitespace-nowrap cursor-pointer select-none ${
                        active ? "text-[#1B2D5C] bg-stone-100" : "text-stone-500 hover:text-stone-800"
                      }`}
                    >
                      <span className="inline-flex items-center gap-1">
                        {prettify(c)}
                        <Icon className={`w-3 h-3 ${active ? "opacity-100" : "opacity-40"}`} />
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan="20" className="p-8 text-center text-stone-500">Loading…</td></tr>
              )}
              {!loading && sortedRows.map((r, i) => (
                <tr key={r.id || r.contract_number || i} className="border-t border-stone-100 hover:bg-stone-50/50">
                  {(data?.columns || []).map((c) => (
                    <td key={c} className={cellClass(c)}>{fmtCell(c, r[c])}</td>
                  ))}
                </tr>
              ))}
              {!loading && sortedRows.length === 0 && (
                <tr><td colSpan="20" className="p-8 text-center text-stone-500">No data</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Month-end Compliance Bundle */}
      <MonthEndBundle />
    </div>
  );
}

function FilterField({ label, children }) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{label}</div>
      {children}
    </div>
  );
}

function prettify(k) {
  return String(k || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
