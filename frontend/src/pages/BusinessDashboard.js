import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  Wallet,
  TrendingUp,
  AlertTriangle,
  Clock,
  Gavel,
  DollarSign,
  Calendar,
  PieChart as PieIcon,
  Info,
  Link2,
  Check,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  Cell,
} from "recharts";

const money = (n) =>
  `$${Number(n || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

// Distinct-but-related navy/teal/coral palette so the concentration bars
// look intentional rather than random. Cycled per top-N client.
const CONCENTRATION_PALETTE = [
  "#1B2D5C", "#243E7B", "#3B5FA5", "#4C7F62", "#7AA98C",
  "#C17767", "#D8967B", "#B45309", "#7C3AED", "#0F766E",
];

export default function BusinessDashboard() {
  const { t } = useLang();
  const [metrics, setMetrics] = useState(null);
  const [cashflow, setCashflow] = useState(null);
  const [copied, setCopied] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  // Global range affects Loaned / Interest / Projected KPIs. Potential Loss
  // stays as a snapshot since it doesn't scale by time window.
  // Range is URL-driven so the view is shareable (?range=weekly).
  const rangeFromUrl = searchParams.get("range");
  const validRanges = ["daily", "weekly", "30d", "ytd"];
  const range = validRanges.includes(rangeFromUrl) ? rangeFromUrl : "30d";
  const setRange = (r) => {
    const next = new URLSearchParams(searchParams);
    if (r && r !== "30d") next.set("range", r);
    else next.delete("range");
    setSearchParams(next, { replace: true });
  };

  useEffect(() => {
    api.get("/business/metrics").then((r) => setMetrics(r.data));
    api.get("/business/cashflow-forecast").then((r) => setCashflow(r.data));
  }, []);

  const copyShareLink = async () => {
    const url = `${window.location.origin}${window.location.pathname}?range=${range}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success(t("share_link_copied") || "Share link copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      // Fallback: show the URL so the owner can copy manually
      window.prompt(t("share_link_prompt") || "Copy this link:", url);
    }
  };

  const rangeData = metrics?.ranges?.[range];
  const rangeLabel = {
    daily: "today",
    weekly: "last 7 days",
    "30d": "last 30 days",
    ytd: "year-to-date",
  }[range];
  const projRangeLabel = {
    daily: "next 24h",
    weekly: "next 7 days",
    "30d": "next 30 days",
    ytd: "rest of year",
  }[range];

  const kpis = [
    {
      key: "loaned",
      label: t("business_current_portfolio") || "Current Portfolio",
      sub: rangeData
        ? `${t("business_new_disbursed") || "New disbursed"} ${rangeLabel}: ${money(rangeData.loaned_new)}`
        : t("business_current_portfolio_sub") || "Principal remaining on all active loans",
      value: metrics ? money(metrics.total_loaned_out) : "—",
      Icon: Wallet,
      tone: "text-[#1B2D5C]",
      to: "/contracts?status=active",
      info: t("info_current_portfolio"),
    },
    {
      key: "earned",
      label: `${t("business_interest_received") || "Interest Received"} · ${rangeLabel}`,
      sub: t("business_interest_received_sub") || "Realized interest collected via payments",
      value: rangeData ? money(rangeData.interest_earned) : "—",
      Icon: DollarSign,
      tone: "text-[#4C7F62]",
      to: "/reports?tab=payments",
      info: t("info_interest_received"),
    },
    {
      key: "proj",
      label: `Projected Interest · ${projRangeLabel}`,
      sub: t("business_projected_sub") || "Expected at current book · capped by Article 4",
      value: rangeData ? money(rangeData.projected_interest) : "—",
      Icon: TrendingUp,
      tone: "text-[#C17767]",
      to: "/reports?tab=financial",
      info: t("info_projected_interest"),
    },
    {
      key: "risk",
      label: t("business_potential_loss") || "Potential Loss",
      sub: t("business_potential_loss_sub") || "If auction items don't sell",
      value: metrics ? money(metrics.potential_loss) : "—",
      Icon: AlertTriangle,
      tone: "text-[#993333]",
      to: "/contracts?status=auction_ready",
      info: t("info_potential_loss"),
    },
  ];

  const statusCards = [
    {
      key: "grace",
      label: t("grace_period") || "Grace Period",
      hint: t("grace_period_hint") || "1–10 days past due",
      value: metrics?.grace_period_count ?? "—",
      Icon: Clock,
      tone: "text-amber-700",
      bg: "bg-amber-50 border-amber-200",
      to: "/contracts?status=grace_period",
      info: t("info_grace_period"),
    },
    {
      key: "auction_ready",
      label: t("ready_for_auction") || "Ready for Auction",
      hint: t("ready_for_auction_hint") || ">10 days past due",
      value: metrics?.auction_ready_count ?? "—",
      Icon: Gavel,
      tone: "text-rose-800",
      bg: "bg-rose-50 border-rose-200",
      to: "/contracts?status=auction_ready",
      info: t("info_auction_ready"),
    },
  ];

  return (
    <div className="space-y-8" data-testid="business-dashboard-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("business") || "Business"}</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
            {t("business_dashboard_title") || "Business Dashboard"}
          </h1>
          <p className="text-stone-600 text-sm mt-1">
            Owner-focused view: cash out, interest earned, projected income, and downside risk.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Button
            onClick={copyShareLink}
            variant="outline"
            size="sm"
            className="gap-1.5 border-[#1B2D5C] text-[#1B2D5C] hover:bg-[#1B2D5C] hover:text-white"
            data-testid="share-snapshot-btn"
            title={t("share_snapshot_hint") || "Copy a link that opens this dashboard on the same range"}
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Link2 className="w-3.5 h-3.5" />}
            {copied ? (t("copied") || "Copied") : (t("share_snapshot") || "Share Snapshot")}
          </Button>
          <div className="inline-flex items-center gap-0.5 p-1 bg-stone-100 rounded-md text-xs" data-testid="range-toggle">
            {[
              { k: "daily", l: "Daily" },
              { k: "weekly", l: "Weekly" },
              { k: "30d", l: "30d" },
              { k: "ytd", l: "YTD" },
            ].map((opt) => (
              <button
                key={opt.k}
                type="button"
                onClick={() => setRange(opt.k)}
                data-testid={`range-${opt.k}`}
                className={`px-3 py-1 rounded transition font-medium ${
                  range === opt.k
                    ? "bg-[#1B2D5C] text-white"
                    : "text-stone-600 hover:text-stone-900"
                }`}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* KPI grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        {kpis.map((c) => (
          <Link
            key={c.key}
            to={c.to}
            data-testid={`biz-kpi-${c.key}`}
            className="p-5 border border-stone-200 rounded-lg bg-white block transition hover:border-[#1B2D5C] hover:shadow-sm"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <div className="text-eyebrow">{c.label}</div>
                  {c.info && (
                    <button
                      type="button"
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
                      title={c.info}
                      aria-label={c.info}
                      data-testid={`biz-kpi-${c.key}-info`}
                      className="text-stone-400 hover:text-[#1B2D5C] transition"
                    >
                      <Info className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <div className="font-display text-2xl md:text-[1.75rem] font-semibold mt-3 break-words">
                  {c.value}
                </div>
                <div className="text-[11px] text-stone-500 mt-2">{c.sub}</div>
              </div>
              <c.Icon className={`w-6 h-6 shrink-0 ${c.tone}`} />
            </div>
          </Link>
        ))}
      </div>

      {/* Grace period + auction-ready status */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
        {statusCards.map((c) => (
          <Link
            key={c.key}
            to={c.to}
            data-testid={`biz-status-${c.key}`}
            className={`p-5 rounded-lg border block transition hover:shadow-sm ${c.bg}`}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-1.5">
                  <div className="text-xs uppercase tracking-wider font-semibold text-stone-700">
                    {c.label}
                  </div>
                  {c.info && (
                    <button
                      type="button"
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
                      title={c.info}
                      aria-label={c.info}
                      data-testid={`biz-status-${c.key}-info`}
                      className="text-stone-400 hover:text-stone-700 transition"
                    >
                      <Info className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <div className={`font-display text-3xl mt-2 ${c.tone}`}>{c.value}</div>
                <div className="text-[11px] text-stone-500 mt-1">{c.hint}</div>
              </div>
              <c.Icon className={`w-10 h-10 ${c.tone} opacity-70`} />
            </div>
          </Link>
        ))}
      </div>

      {/* Cash-flow: past actual vs future forecast */}
      <Card className="p-5 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="biz-cashflow">
        <div className="flex items-end justify-between mb-4 flex-wrap gap-2">
          <div>
            <div className="text-eyebrow">Cash Flow · 30d Actual vs 30d Forecast</div>
            <h2 className="font-display text-lg md:text-xl mt-1">
              {cashflow ? money(cashflow.total_actual_in) : "—"}
              <span className="text-sm text-stone-500 font-normal ml-2">actual (last 30d)</span>
              <span className="mx-2 text-stone-300">·</span>
              {cashflow ? money(cashflow.total_expected_in) : "—"}
              <span className="text-sm text-stone-500 font-normal ml-2">expected (next 30d)</span>
            </h2>
          </div>
          <div className="flex items-center gap-1 text-xs text-stone-500">
            <Calendar className="w-3.5 h-3.5" /> Overlay of receipted payments vs projected due-date inflows
          </div>
        </div>
        <div className="h-72" data-testid="biz-cashflow-chart">
          {cashflow?.days && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cashflow.days} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => d.slice(5)}
                  tick={{ fontSize: 10, fill: "#78716C" }}
                  interval={4}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#78716C" }}
                  tickFormatter={(v) => (v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`)}
                />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: "#D6D3D1" }}
                  formatter={(v, name) => [money(v), name === "actual_in" ? "Actual" : "Forecast"]}
                  labelFormatter={(l) => `Date ${l}`}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                  formatter={(v) => (v === "actual_in" ? "Actual (past 30d)" : "Forecast (next 30d)")}
                />
                <Bar dataKey="actual_in" fill="#4C7F62" radius={[3, 3, 0, 0]} />
                <Bar dataKey="expected_in" fill="#1B2D5C" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      {/* Client concentration — who holds the biggest slice of the book? */}
      <Card className="p-5 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="biz-concentration">
        <div className="flex items-end justify-between mb-4 flex-wrap gap-2">
          <div>
            <div className="text-eyebrow">Client Concentration Risk</div>
            <h2 className="font-display text-lg md:text-xl mt-1">
              Top 10 clients · <span className="text-sm text-stone-500 font-normal">by outstanding principal</span>
            </h2>
          </div>
          <div className="flex items-center gap-1 text-xs text-stone-500">
            <PieIcon className="w-3.5 h-3.5" /> Higher concentration = higher default risk in a few borrowers
          </div>
        </div>
        <div className="h-72" data-testid="biz-concentration-chart">
          {metrics?.client_concentration?.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={metrics.client_concentration}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 10, fill: "#78716C" }}
                  tickFormatter={(v) => (v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`)}
                />
                <YAxis
                  type="category"
                  dataKey="client_name"
                  tick={{ fontSize: 11, fill: "#44403C" }}
                  width={150}
                />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: "#D6D3D1" }}
                  formatter={(v, _, entry) => [
                    `${money(v)} (${entry.payload.percent}%)`,
                    "Principal",
                  ]}
                />
                <Bar dataKey="principal" radius={[0, 3, 3, 0]}>
                  {metrics.client_concentration.map((row, i) => (
                    <Cell
                      key={i}
                      fill={row.client_name === "Others" ? "#A8A29E" : CONCENTRATION_PALETTE[i % CONCENTRATION_PALETTE.length]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-stone-400 text-sm">
              No active loans to chart yet.
            </div>
          )}
        </div>
      </Card>

      {/* Per-loan breakdown */}
      <Card className="p-0 border border-stone-200 shadow-none rounded-lg bg-white overflow-hidden" data-testid="biz-per-loan">
        <div className="p-5 border-b border-stone-200">
          <div className="text-eyebrow">Per-Loan Breakdown</div>
          <h2 className="font-display text-lg mt-1">Top 20 by Principal</h2>
          <p className="text-xs text-stone-500 mt-1">
            Interest earned = already paid via receipts. Projected 30d = next billing month (capped by Article 4).
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="biz-per-loan-table">
            <thead className="bg-stone-50 text-left text-xs uppercase tracking-wider text-stone-500 font-semibold">
              <tr>
                <th className="px-4 py-3">Contract</th>
                <th className="px-4 py-3">Client</th>
                <th className="px-4 py-3">Item</th>
                <th className="px-4 py-3 text-right">Principal</th>
                <th className="px-4 py-3 text-right">Rate</th>
                <th className="px-4 py-3 text-right">Interest Earned</th>
                <th className="px-4 py-3 text-right">Projected 30d</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {(metrics?.per_loan || []).slice(0, 20).map((r) => (
                <tr key={r.contract_id} className="border-t border-stone-100 hover:bg-stone-50/50">
                  <td className="px-4 py-3 font-medium whitespace-nowrap">
                    <Link to={`/payments?contract=${r.contract_number}`} className="text-[#1B2D5C] hover:underline">
                      {r.contract_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{r.client_name || "—"}</td>
                  <td className="px-4 py-3">
                    <span className="text-[10px] uppercase tracking-wider text-stone-500 bg-stone-100 border border-stone-200 rounded px-1.5 py-0.5">
                      {r.item_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium tabular-nums">{money(r.principal_remaining)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.interest_rate}%</td>
                  <td className="px-4 py-3 text-right tabular-nums text-emerald-700">{money(r.interest_earned)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#C17767]">{money(r.interest_projected_30d)}</td>
                  <td className="px-4 py-3">
                    <StatusPill status={r.status} />
                  </td>
                </tr>
              ))}
              {(!metrics || !metrics.per_loan?.length) && (
                <tr>
                  <td colSpan="8" className="p-8 text-center text-stone-500">
                    No active loans
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    active: "bg-emerald-50 text-emerald-800 border-emerald-200",
    overdue: "bg-amber-50 text-amber-800 border-amber-200",
    auction_ready: "bg-rose-100 text-rose-800 border-rose-300",
  };
  const cls = map[status] || "bg-stone-100 text-stone-700 border-stone-200";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${cls}`}>
      {String(status || "—").replace(/_/g, " ")}
    </span>
  );
}
