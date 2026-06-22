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
} from "lucide-react";

// 6 report tabs from user spec
const TABS = [
  { key: "active-contracts", labelKey: "active_contract",
    kpis: ["total_contracts", "total_loan", "tax_accumulate", "almost_expired"] },
  { key: "payments", labelKey: "payments",
    kpis: ["total_transactions", "total_payments", "interest_received", "total_penalty"] },
  { key: "overdue", labelKey: "total_overdue",
    kpis: ["total_overdue", "total_outstanding", "total_interest", "near_expired"] },
  { key: "auction", labelKey: "auctions",
    kpis: ["total_auction", "total_amount"] },
  { key: "inventory", labelKey: "inventory",
    kpis: ["total_items", "total_amount", "active_items", "overdue_items"] },
  { key: "financial", labelKey: "financial",
    kpis: ["total_loan", "total_payment", "interest_received", "profit"] },
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
    minimumFractionDigits: 2, maximumFractionDigits: 2,
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

export default function Reports() {
  const { t } = useLang();
  const [tab, setTab] = useState("active-contracts");
  const [filters, setFilters] = useState({ month: "", year: "", category: "", sub_category: "" });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

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
        <h1 className="font-display text-4xl font-semibold mt-1">
          {t(currentTab?.labelKey || "reports")}
        </h1>
      </header>

      {/* Tab navigation — navy pill style from mockup */}
      <div className="flex flex-wrap gap-2 print:hidden" data-testid="report-tabs">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            data-testid={`report-tab-${tb.key}`}
            className={`px-4 py-2.5 text-sm font-medium tracking-wide rounded-md transition ${
              tab === tb.key
                ? "bg-[#2F4F4F] text-white shadow"
                : "bg-stone-100 text-stone-700 hover:bg-stone-200"
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
            <Button onClick={load} className="bg-[#2F4F4F] hover:bg-[#1D3333]" data-testid="filter-apply">
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
              className="inline-flex items-center gap-1 px-3 py-2 rounded-md text-sm border border-stone-200 bg-white hover:bg-[#993333] hover:text-white hover:border-[#993333] transition"
              data-testid="report-pdf"
            >
              <FileText className="w-4 h-4" /> {t("pdf")}
            </a>
            <a
              href={exportUrl("xlsx")}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-3 py-2 rounded-md text-sm border border-stone-200 bg-white hover:bg-[#4C7F62] hover:text-white hover:border-[#4C7F62] transition"
              data-testid="report-excel"
            >
              <FileSpreadsheet className="w-4 h-4" /> {t("excel")}
            </a>
          </div>
        </div>
      </Card>

      {/* KPI cards */}
      <div className={`grid gap-4 ${currentTab.kpis.length === 2 ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1 md:grid-cols-2 lg:grid-cols-4"}`}>
        {currentTab.kpis.map((k) => {
          const v = data?.kpis?.[k];
          return (
            <Card
              key={k}
              className="p-6 border border-stone-200 shadow-none rounded-lg bg-white"
              data-testid={`kpi-${k}`}
            >
              <div className="text-eyebrow">{t(k) === k ? prettify(k) : t(k)}</div>
              <div className="font-display text-3xl font-semibold mt-3 text-stone-900">
                {data == null ? "…" : MONEY_KEYS.has(k) ? fmtMoney(v) : v ?? "—"}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Detail table */}
      <Card className="border border-stone-200 shadow-none rounded-lg bg-white overflow-hidden">
        <div className="px-6 pt-5 pb-3 border-b border-stone-200">
          <div className="text-eyebrow">Detail</div>
          <div className="font-display text-lg mt-1 text-stone-900">
            {t(currentTab.labelKey)} · {data?.rows?.length ?? 0} rows
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="report-table">
            <thead className="bg-stone-50 text-left">
              <tr>
                {(data?.columns || []).map((c) => (
                  <th
                    key={c}
                    className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold whitespace-nowrap"
                  >
                    {prettify(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan="20" className="p-8 text-center text-stone-500">Loading…</td></tr>
              )}
              {!loading && (data?.rows || []).map((r, i) => (
                <tr key={r.id || r.contract_number || i} className="border-t border-stone-100">
                  {(data?.columns || []).map((c) => (
                    <td key={c} className="px-4 py-3 whitespace-nowrap">{fmtCell(c, r[c])}</td>
                  ))}
                </tr>
              ))}
              {!loading && (data?.rows || []).length === 0 && (
                <tr><td colSpan="20" className="p-8 text-center text-stone-500">No data</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
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
