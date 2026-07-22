import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import {
  Wallet,
  TrendingUp,
  AlertTriangle,
  Clock,
  Gavel,
  DollarSign,
  Calendar,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

const money = (n) =>
  `$${Number(n || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

export default function BusinessDashboard() {
  const { t } = useLang();
  const [metrics, setMetrics] = useState(null);
  const [cashflow, setCashflow] = useState(null);

  useEffect(() => {
    api.get("/business/metrics").then((r) => setMetrics(r.data));
    api.get("/business/cashflow-forecast").then((r) => setCashflow(r.data));
  }, []);

  const kpis = [
    {
      key: "loaned",
      label: t("business_total_loaned") || "Total Loaned Out",
      sub: t("business_total_loaned_sub") || "Cash currently in the field",
      value: metrics ? money(metrics.total_loaned_out) : "—",
      Icon: Wallet,
      tone: "text-[#1B2D5C]",
      to: "/contracts?status=active",
    },
    {
      key: "earned",
      label: t("business_interest_ytd") || "Interest Earned YTD",
      sub: t("business_interest_ytd_sub") || "Realized interest — this year",
      value: metrics ? money(metrics.interest_earned_ytd) : "—",
      Icon: DollarSign,
      tone: "text-[#4C7F62]",
      to: "/reports?tab=payments",
    },
    {
      key: "proj",
      label: t("business_proj_30d") || "Projected Interest · 30d",
      sub: t("business_proj_30d_sub") || "Next month at current book",
      value: metrics ? money(metrics.projected_interest_30d) : "—",
      Icon: TrendingUp,
      tone: "text-[#C17767]",
      to: "/reports?tab=financial",
    },
    {
      key: "risk",
      label: t("business_potential_loss") || "Potential Loss",
      sub: t("business_potential_loss_sub") || "If auction items don't sell",
      value: metrics ? money(metrics.potential_loss) : "—",
      Icon: AlertTriangle,
      tone: "text-[#993333]",
      to: "/contracts?status=auction_ready",
    },
  ];

  const statusCards = [
    {
      key: "grace",
      label: t("grace_period") || "Grace Period · Masa Tenggang",
      hint: t("grace_period_hint") || "1–10 days past due",
      value: metrics?.grace_period_count ?? "—",
      Icon: Clock,
      tone: "text-amber-700",
      bg: "bg-amber-50 border-amber-200",
      to: "/contracts?status=overdue",
    },
    {
      key: "auction_ready",
      label: t("ready_for_auction") || "Ready for Auction · Siap Lelang",
      hint: t("ready_for_auction_hint") || ">10 days past due",
      value: metrics?.auction_ready_count ?? "—",
      Icon: Gavel,
      tone: "text-rose-800",
      bg: "bg-rose-50 border-rose-200",
      to: "/contracts?status=auction_ready",
    },
  ];

  return (
    <div className="space-y-8" data-testid="business-dashboard-root">
      <header>
        <div className="text-eyebrow">{t("business") || "Business"}</div>
        <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
          {t("business_dashboard_title") || "Business Dashboard"}
        </h1>
        <p className="text-stone-600 text-sm mt-1">
          Owner-focused view: cash out, interest earned, projected income, and downside risk.
        </p>
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
                <div className="text-eyebrow">{c.label}</div>
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
                <div className="text-xs uppercase tracking-wider font-semibold text-stone-700">
                  {c.label}
                </div>
                <div className={`font-display text-3xl mt-2 ${c.tone}`}>{c.value}</div>
                <div className="text-[11px] text-stone-500 mt-1">{c.hint}</div>
              </div>
              <c.Icon className={`w-10 h-10 ${c.tone} opacity-70`} />
            </div>
          </Link>
        ))}
      </div>

      {/* Cash-flow forecast chart */}
      <Card className="p-5 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="biz-cashflow">
        <div className="flex items-end justify-between mb-4 flex-wrap gap-2">
          <div>
            <div className="text-eyebrow">Cash Flow Forecast · 30 Days</div>
            <h2 className="font-display text-lg md:text-xl mt-1">
              {cashflow ? money(cashflow.total_expected_in) : "—"}
              <span className="text-sm text-stone-500 font-normal ml-2">expected inflow</span>
            </h2>
          </div>
          <div className="flex items-center gap-1 text-xs text-stone-500">
            <Calendar className="w-3.5 h-3.5" /> Based on due dates of active/overdue contracts
          </div>
        </div>
        <div className="h-64" data-testid="biz-cashflow-chart">
          {cashflow?.days && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cashflow.days} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => d.slice(5)}
                  tick={{ fontSize: 10, fill: "#78716C" }}
                  interval={2}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#78716C" }}
                  tickFormatter={(v) => (v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`)}
                />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: "#D6D3D1" }}
                  formatter={(v) => [money(v), "Expected"]}
                  labelFormatter={(l) => `Due ${l}`}
                />
                <Bar dataKey="expected_in" fill="#1B2D5C" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
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
