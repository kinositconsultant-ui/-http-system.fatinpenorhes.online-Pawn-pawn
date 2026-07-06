import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import PinnedViewsPanel from "../components/PinnedViewsPanel";
import {
  Users,
  FileText,
  AlertCircle,
  Wallet,
  TrendingUp,
  Banknote,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

const moneyFmt = (n) =>
  `USD ${Number(n || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

export default function Dashboard() {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [trends, setTrends] = useState(null);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setData(r.data));
    api.get("/dashboard/trends").then((r) => setTrends(r.data));
  }, []);

  const cards = [
    {
      key: "clients",
      label: t("total_clients"),
      value: data?.total_clients ?? "—",
      Icon: Users,
      tone: "text-[#1B2D5C]",
      testid: "kpi-clients",
    },
    {
      key: "active",
      label: t("active_contracts"),
      value: data?.active_contracts ?? "—",
      Icon: FileText,
      tone: "text-[#4C7F62]",
      testid: "kpi-active",
    },
    {
      key: "overdue",
      label: t("overdue_contracts"),
      value: data?.overdue_contracts ?? "—",
      Icon: AlertCircle,
      tone: "text-[#993333]",
      testid: "kpi-overdue",
    },
    {
      key: "loan",
      label: t("total_loan_amount"),
      value: data ? moneyFmt(data.total_loan_amount) : "—",
      Icon: Banknote,
      tone: "text-[#1B2D5C]",
      testid: "kpi-loan",
    },
    {
      key: "payments",
      label: t("total_payments"),
      value: data ? moneyFmt(data.total_payments) : "—",
      Icon: Wallet,
      tone: "text-[#1B2D5C]",
      testid: "kpi-payments",
    },
    {
      key: "profit",
      label: t("profit_summary"),
      value: data ? moneyFmt(data.total_interest_expected) : "—",
      Icon: TrendingUp,
      tone: "text-[#C17767]",
      testid: "kpi-profit",
    },
  ];

  return (
    <div className="space-y-8" data-testid="dashboard-root">
      <header>
        <div className="text-eyebrow">{t("overview")}</div>
        <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold text-stone-900 mt-1">
          {t("dashboard")}
        </h1>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
        {cards.map((c) => (
          <Card
            key={c.key}
            className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white"
            data-testid={c.testid}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="text-eyebrow">{c.label}</div>
                <div className="font-display text-2xl md:text-3xl font-semibold mt-3 break-words">
                  {c.value}
                </div>
              </div>
              <c.Icon className={`w-6 h-6 shrink-0 ${c.tone}`} />
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
        <Card className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white lg:col-span-2" data-testid="chart-trends">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-eyebrow">{t("monthly_trends")}</div>
              <div className="font-display text-lg mt-1">{t("monthly_trends_sub")}</div>
            </div>
          </div>
          <div className="h-64 md:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends?.months || []}>
                <defs>
                  <linearGradient id="gLoans" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#1B2D5C" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#1B2D5C" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gPays" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#C17767" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#C17767" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" vertical={false} />
                <XAxis dataKey="month" stroke="#57534E" tick={{ fontSize: 12 }} />
                <YAxis stroke="#57534E" tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "#fff",
                    border: "1px solid #E7E5E4",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area
                  type="monotone"
                  dataKey="loans"
                  stroke="#1B2D5C"
                  fill="url(#gLoans)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="payments"
                  stroke="#C17767"
                  fill="url(#gPays)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="interest"
                  stroke="#8F9779"
                  fill="transparent"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="chart-overdue">
          <div className="text-eyebrow">{t("overdue_by_type")}</div>
          <div className="font-display text-lg mt-1 mb-4">{t("contracts_past_due")}</div>
          <div className="h-64 md:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trends?.overdue_by_type || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" vertical={false} />
                <XAxis dataKey="type" stroke="#57534E" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} stroke="#57534E" tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "#fff",
                    border: "1px solid #E7E5E4",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill="#993333" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white">
        <div className="text-eyebrow mb-3">{t("status")}</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label={t("active_contracts")} value={data?.active_contracts} />
          <Stat label={t("overdue_contracts")} value={data?.overdue_contracts} tone="text-[#993333]" />
          <Stat label={t("redeemed")} value={data?.redeemed_contracts} tone="text-[#4C7F62]" />
          <Stat label={t("auction")} value={data?.auction_contracts} tone="text-[#C17767]" />
        </div>
      </Card>

      <PinnedViewsPanel />
    </div>
  );
}

function Stat({ label, value, tone = "text-stone-900" }) {
  return (
    <div className="p-4 rounded-md bg-stone-50 border border-stone-100">
      <div className="text-xs text-stone-500">{label}</div>
      <div className={`font-display text-2xl mt-1 ${tone}`}>{value ?? "—"}</div>
    </div>
  );
}
