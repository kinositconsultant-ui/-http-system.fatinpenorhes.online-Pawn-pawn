import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import {
  Users,
  FileText,
  AlertCircle,
  Wallet,
  TrendingUp,
  Banknote,
} from "lucide-react";

const moneyFmt = (n) =>
  `USD ${Number(n || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

export default function Dashboard() {
  const { t } = useLang();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setData(r.data));
  }, []);

  const cards = [
    {
      key: "clients",
      label: t("total_clients"),
      value: data?.total_clients ?? "—",
      Icon: Users,
      tone: "text-[#2F4F4F]",
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
      tone: "text-[#2F4F4F]",
      testid: "kpi-loan",
    },
    {
      key: "payments",
      label: t("total_payments"),
      value: data ? moneyFmt(data.total_payments) : "—",
      Icon: Wallet,
      tone: "text-[#2F4F4F]",
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
        <h1 className="font-display text-4xl font-semibold text-stone-900 mt-1">
          {t("dashboard")}
        </h1>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-3 gap-6">
        {cards.map((c) => (
          <Card
            key={c.key}
            className="p-6 border border-stone-200 shadow-none rounded-lg bg-white"
            data-testid={c.testid}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="text-eyebrow">{c.label}</div>
                <div className="font-display text-3xl font-semibold mt-3">
                  {c.value}
                </div>
              </div>
              <c.Icon className={`w-6 h-6 ${c.tone}`} />
            </div>
          </Card>
        ))}
      </div>

      <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white">
        <div className="text-eyebrow mb-3">{t("status")}</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label={t("active_contracts")} value={data?.active_contracts} />
          <Stat label={t("overdue_contracts")} value={data?.overdue_contracts} tone="text-[#993333]" />
          <Stat label={t("redeemed")} value={data?.redeemed_contracts} tone="text-[#4C7F62]" />
          <Stat label={t("auction")} value={data?.auction_contracts} tone="text-[#C17767]" />
        </div>
      </Card>
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
