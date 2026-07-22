import { useEffect, useMemo, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
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
  Copy,
} from "lucide-react";
import { toast } from "sonner";
import MonthEndBundle from "../components/MonthEndBundle";
import SavedViews from "../components/SavedViews";

// 6 report tabs from user spec — each with a distinct accent color
// Row-count thresholds that turn a tab badge red + pulse when exceeded.
// These are the counts at which the number becomes a "call to action" for the
// owner. Only "overdue" is watched by default — auction ready is expected
// to stay elevated so we don't alert on it.
const TAB_ALERT_THRESHOLDS = {
  overdue: 15,
};

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
    kpis: ["total_loan", "total_payment", "interest_received", "profit", "penalty_paid", "penalty_outstanding"] },
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
  // Nov-2026 spec: normalized fields
  "original_loan_amount", "current_principal", "principal_paid",
  "interest_charged", "interest_paid", "interest_outstanding",
  "penalty_charged", "penalty_paid", "penalty_outstanding",
  "total_amount_due", "total_payments_received",
  // Auction split
  "auction_capital_recovered", "auction_realized_profit", "auction_realized_loss",
]);

const fmtMoney = (v) => {
  const n = Number(v ?? 0);
  return `$${n.toLocaleString("en-US", {
    minimumFractionDigits: 0, maximumFractionDigits: 2,
  })}`;
};

const fmtCell = (col, v, row) => {
  if (col === "status" && row?.is_auction_eligible) {
    // Render a compact status + red AUCTION ELIGIBLE pill so the auctioneer
    // can spot rows that are past the 10-day tolerance and have hit the
    // Article 4 two-month interest cap (no further accrual pressure).
    return (
      <div className="flex items-center gap-1.5 flex-wrap" data-testid="auction-eligible-row">
        <span className="text-xs px-1.5 py-0.5 rounded-md border border-stone-300 bg-white uppercase tracking-wider font-medium">
          {String(v || "—").replace(/_/g, " ")}
        </span>
        <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-rose-100 text-rose-800 border border-rose-300 whitespace-nowrap">
          Auction Eligible
        </span>
      </div>
    );
  }
  if (col === "phone" && v) {
    // Tap-to-dial on mobile; small copy button on desktop.
    return <PhoneCell value={String(v)} />;
  }
  if (v == null || v === "") return "—";
  if (MONEY_KEYS.has(col)) return fmtMoney(v);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
};

function PhoneCell({ value }) {
  const clean = value.replace(/\s+/g, "");
  const onCopy = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`Copied ${value}`);
    } catch {
      toast.error("Copy failed");
    }
  };
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap" data-testid="phone-cell">
      <a
        href={`tel:${clean}`}
        className="text-[#1B2D5C] hover:underline font-medium"
        onClick={(e) => e.stopPropagation()}
        title="Tap to call"
      >
        {value}
      </a>
      <button
        type="button"
        onClick={onCopy}
        className="inline-flex items-center justify-center w-5 h-5 rounded hover:bg-stone-200 text-stone-500 hover:text-[#1B2D5C]"
        title="Copy number"
        aria-label={`Copy ${value}`}
        data-testid="phone-copy-btn"
      >
        <Copy className="w-3 h-3" />
      </button>
    </span>
  );
}

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

// Short display labels for verbose columns so headers don't blow out the
// table width. Wrapping is also allowed on headers (see <th> below).
const COL_SHORT_LABEL = {
  original_loan_amount: "Original Loan",
  current_principal: "Current Principal",
  paid_amount: "Paid",
  interest_received: "Interest Rcvd",
  interest_charged: "Interest Charged",
  interest_paid: "Interest Paid",
  interest_outstanding: "Interest Due",
  penalty_paid: "Penalty Paid",
  penalty_outstanding: "Penalty Due",
  penalty_charged: "Penalty Charged",
  principal_remaining: "Principal Left",
  principal_paid: "Principal Paid",
  total_amount_due: "Total Due",
  total_payments_received: "Total Received",
  auction_capital_recovered: "Capital Rec.",
  auction_realized_profit: "Realized Profit",
  auction_realized_loss: "Realized Loss",
  contract_number: "Contract #",
  receipt_number: "Receipt #",
  contract_date: "Contract Date",
  due_date: "Due Date",
  days_overdue: "Days Overdue",
  client_name: "Client",
  phone: "Phone",
  starting_price: "Start Price",
  sold_price: "Sold Price",
  manufacture_year: "Mfg Year",
  payment_method: "Method",
  interest_rate: "Rate",
};

const cellClass = (col) => {
  const base = "px-2.5 py-2 align-top";
  if (WIDE_KEYS.has(col)) return `${base} whitespace-normal break-words max-w-[220px]`;
  if (NO_WRAP_KEYS.has(col)) return `${base} whitespace-nowrap`;
  return `${base} whitespace-nowrap`;
};

export default function Reports() {
  const { t } = useLang();
  const [searchParams, setSearchParams] = useSearchParams();
  // URL-driven initial tab so Dashboard KPI cards can deep-link straight into
  // e.g. /reports?tab=financial. Falls back to active-contracts.
  const initialTab = (() => {
    const q = searchParams.get("tab");
    const valid = TABS.some((r) => r.key === q);
    return valid ? q : "active-contracts";
  })();
  const [tab, setTab] = useState(initialTab);
  const [filters, setFilters] = useState({ month: "", year: "", category: "", sub_category: "" });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  // Client-side sort: null = server order, otherwise { key, dir: "asc" | "desc" }
  const [sort, setSort] = useState(null);
  // Row-count per tab (fetched once on mount for tab badges)
  const [tabCounts, setTabCounts] = useState({});

  // Keep the URL param in sync whenever the user switches tabs so links and
  // browser back/forward preserve the current tab.
  const changeTab = useCallback(
    (nextKey) => {
      setTab(nextKey);
      const next = new URLSearchParams(searchParams);
      if (nextKey === "active-contracts") next.delete("tab");
      else next.set("tab", nextKey);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/reports/v2-counts");
        setTabCounts(data || {});
      } catch { /* non-fatal */ }
    })();
  }, []);

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

  // Auto-apply a pending view handed off by the Dashboard "Pinned Views" panel.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("pending-report-view");
      if (!raw) return;
      sessionStorage.removeItem("pending-report-view");
      const v = JSON.parse(raw);
      if (!v?.tab) return;
      setFilters({
        month: v.filters?.month || "",
        year: v.filters?.year || "",
        category: v.filters?.category || "",
        sub_category: v.filters?.sub_category || "",
      });
      setTab(v.tab);
      setTimeout(() => setSort(v.sort || null), 0);
    } catch { /* malformed sessionStorage value */ }
  }, []);

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

  const applySavedView = ({ tab: nextTab, filters: nextFilters, sort: nextSort }) => {
    // Apply in a specific order so the effect that resets sort on tab-change
    // doesn't wipe the sort we're trying to apply.
    setFilters({
      month: nextFilters?.month || "",
      year: nextFilters?.year || "",
      category: nextFilters?.category || "",
      sub_category: nextFilters?.sub_category || "",
    });
    if (nextTab !== tab) {
      setTab(nextTab);
      // The [tab] effect clears sort — restore it on the next tick.
      setTimeout(() => setSort(nextSort || null), 0);
    } else {
      setSort(nextSort || null);
    }
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
        {TABS.map((tb) => {
          const count = tabCounts[tb.key];
          const isActive = tab === tb.key;
          const threshold = TAB_ALERT_THRESHOLDS[tb.key];
          const alerting = threshold != null && count != null && count > threshold;
          return (
            <button
              key={tb.key}
              onClick={() => changeTab(tb.key)}
              data-testid={`report-tab-${tb.key}`}
              style={isActive ? { backgroundColor: tb.color, color: "white" } : undefined}
              className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium tracking-wide rounded-md transition shadow-sm ${
                isActive ? "shadow-md" : `${tb.soft} hover:opacity-90`
              } ${alerting && !isActive ? "ring-2 ring-red-300 ring-offset-1" : ""}`}
            >
              <span>{t(tb.labelKey)}</span>
              {count != null && (
                <span
                  className={`text-[10px] font-semibold tabular-nums px-1.5 py-0.5 rounded-full ${
                    alerting
                      ? isActive
                        ? "bg-red-100 text-red-700 animate-pulse"
                        : "bg-red-600 text-white animate-pulse"
                      : isActive
                        ? "bg-white/25 text-white"
                        : "bg-white/70 text-stone-700"
                  }`}
                  data-testid={`report-tab-count-${tb.key}`}
                  title={alerting ? `Alert: ${count} exceeds threshold ${threshold}` : undefined}
                >
                  {count.toLocaleString()}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Saved Views strip */}
      <SavedViews tab={tab} filters={filters} sort={sort} onApply={applySavedView} />

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
                      className={`px-2 py-2 text-[10px] uppercase tracking-wider font-semibold cursor-pointer select-none align-bottom leading-tight ${
                        active ? "text-[#1B2D5C] bg-stone-100" : "text-stone-500 hover:text-stone-800"
                      }`}
                    >
                      <span className="inline-flex items-start gap-1">
                        <span className="whitespace-normal break-words">
                          {COL_SHORT_LABEL[c] || prettify(c)}
                        </span>
                        <Icon className={`w-3 h-3 shrink-0 mt-0.5 ${active ? "opacity-100" : "opacity-40"}`} />
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
                    <td key={c} className={cellClass(c)}>{fmtCell(c, r[c], r)}</td>
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
