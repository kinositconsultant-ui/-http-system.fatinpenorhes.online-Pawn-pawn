import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "./ui/card";
import {
  Server,
  Wallet,
  Clock,
  Database,
  Bell,
  Package,
  ExternalLink,
  FileText,
  Landmark,
  ShieldCheck,
} from "lucide-react";

const fmtUSD = (n) =>
  n == null
    ? "—"
    : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

const fmtDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
};

/** One-line row of a scheduler job. */
function JobRow({ Icon, label, at, lastRun }) {
  const relTime = (iso) => {
    if (!iso) return null;
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return null;
    const diff = Date.now() - t;
    const min = Math.floor(diff / 60000);
    if (min < 1) return "just now";
    if (min < 60) return `${min}m ago`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  };
  return (
    <div className="flex items-center gap-2 py-1.5 text-xs">
      <Icon className="w-3.5 h-3.5 text-stone-500" />
      <div className="flex-1 flex items-center gap-1.5 min-w-0">
        <span className="text-stone-600 truncate">{label}</span>
        {lastRun && (
          <span
            className={`text-[9px] px-1.5 py-0.5 rounded-full border tabular-nums ${
              lastRun.status === "ok"
                ? "bg-emerald-50 text-emerald-700 border-emerald-100"
                : "bg-red-50 text-red-700 border-red-100"
            }`}
            title={`Last run ${relTime(lastRun.at)}${
              lastRun.duration_ms ? ` · ${lastRun.duration_ms}ms` : ""
            }${lastRun.status === "failed" && lastRun.details?.error ? ` · ${lastRun.details.error}` : ""}`}
            data-testid={`sys-last-run-${lastRun.job_id}`}
          >
            {lastRun.status === "ok" ? "✓" : "✕"} {relTime(lastRun.at)}
          </span>
        )}
      </div>
      <span className="text-stone-800 font-medium tabular-nums">{fmtDate(at)}</span>
    </div>
  );
}

/** Small stat block for the finance summary card. */
function FinanceStat({ label, value, tone = "text-stone-900", testid }) {
  return (
    <div className="flex flex-col" data-testid={testid}>
      <span className="text-[10px] uppercase tracking-wider text-stone-500">
        {label}
      </span>
      <span className={`font-display text-lg mt-0.5 ${tone}`}>{value}</span>
    </div>
  );
}

/** Quick-nav pill. */
function QuickLink({ to, Icon, label, testid }) {
  return (
    <Link
      to={to}
      data-testid={testid}
      className="group flex items-center gap-2 px-3 py-2 rounded-md border border-stone-200 bg-white hover:border-[#1B2D5C]/40 hover:bg-[#1B2D5C]/5 transition text-xs text-stone-700"
    >
      <Icon className="w-3.5 h-3.5 text-[#1B2D5C]" />
      <span className="flex-1">{label}</span>
      <ExternalLink className="w-3 h-3 text-stone-300 group-hover:text-[#1B2D5C]" />
    </Link>
  );
}

export default function SystemManagementPanel() {
  const { t } = useLang();
  const [schedule, setSchedule] = useState(null);
  const [finance, setFinance] = useState(null);

  useEffect(() => {
    (async () => {
      // Both endpoints are admin-only; fail silently for non-admins so the
      // panel just shows the parts they can see.
      try {
        const { data } = await api.get("/admin/backups/schedule");
        setSchedule(data);
      } catch { /* ignore */ }
      try {
        const { data } = await api.get("/finance/summary");
        setFinance(data);
      } catch { /* ignore */ }
    })();
  }, []);

  const hasAny = schedule || finance;
  if (!hasAny) return null; // non-admin: hide the whole panel

  return (
    <section
      className="mt-2"
      data-testid="system-management-panel"
    >
      <div className="flex items-center gap-2 mb-3">
        <Server className="w-4 h-4 text-[#1B2D5C]" />
        <div className="text-eyebrow">System Management &amp; Finance</div>
        <span className="text-stone-300">·</span>
        <span className="text-[10px] uppercase tracking-[0.22em] text-stone-400 font-medium">
          Fatin Penhores
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
        {/* Scheduler status */}
        {schedule && (
          <Card
            className="p-4 md:p-5 border border-stone-200 shadow-none rounded-lg bg-white"
            data-testid="sys-scheduler-card"
          >
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-4 h-4 text-[#1B2D5C]" />
              <div className="font-display text-base text-stone-900">
                Scheduler
              </div>
              <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
                running
              </span>
            </div>
            <JobRow Icon={Database} label="Daily backup" at={schedule.next_run_at} lastRun={schedule.last_runs?.daily_backup} />
            <JobRow Icon={Bell} label="WhatsApp reminders" at={schedule.next_reminders_run_at} lastRun={schedule.last_runs?.daily_reminders} />
            <JobRow Icon={Package} label="Month-end bundle" at={schedule.next_monthend_run_at} lastRun={schedule.last_runs?.monthend_bundle} />
            <JobRow Icon={ShieldCheck} label="Alert digest" at={schedule.next_alert_digest_run_at} lastRun={schedule.last_runs?.alert_digest} />
            <div className="text-[10px] text-stone-400 mt-3">
              Retention: last {schedule.retention} backups
            </div>
          </Card>
        )}

        {/* Finance snapshot */}
        {finance && (
          <Card
            className="p-4 md:p-5 border border-stone-200 shadow-none rounded-lg bg-white"
            data-testid="sys-finance-card"
          >
            <div className="flex items-center gap-2 mb-3">
              <Landmark className="w-4 h-4 text-[#1B2D5C]" />
              <div className="font-display text-base text-stone-900">Finance</div>
              <Link
                to="/finance"
                className="ml-auto text-[10px] text-[#1B2D5C] hover:underline underline-offset-2"
                data-testid="sys-finance-open"
              >
                Open →
              </Link>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <FinanceStat
                label="Cash on hand"
                value={fmtUSD(finance.cash_on_hand)}
                tone={finance.cash_on_hand < 0 ? "text-red-600" : "text-stone-900"}
                testid="sys-cash-on-hand"
              />
              <FinanceStat
                label="Capital outstanding"
                value={fmtUSD(finance.capital_outstanding)}
                testid="sys-capital-out"
              />
              <FinanceStat
                label="Interest received"
                value={fmtUSD(finance.interest_received)}
                tone="text-emerald-700"
                testid="sys-interest-recv"
              />
              <FinanceStat
                label="Expenses (month)"
                value={fmtUSD(finance.expenses_period ?? finance.expenses_total)}
                tone="text-amber-700"
                testid="sys-expenses-month"
              />
            </div>
            <div className="pt-3 border-t border-stone-100 flex items-center justify-between text-xs">
              <span className="text-stone-500">Net profit</span>
              <span
                className={`font-display text-lg ${
                  (finance.net_profit ?? 0) >= 0 ? "text-emerald-700" : "text-red-600"
                }`}
                data-testid="sys-net-profit"
              >
                {fmtUSD(finance.net_profit)}
              </span>
            </div>
          </Card>
        )}

        {/* Quick actions */}
        <Card
          className="p-4 md:p-5 border border-stone-200 shadow-none rounded-lg bg-white"
          data-testid="sys-quicknav-card"
        >
          <div className="flex items-center gap-2 mb-3">
            <Wallet className="w-4 h-4 text-[#1B2D5C]" />
            <div className="font-display text-base text-stone-900">
              Quick access
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2">
            <QuickLink to="/finance" Icon={Landmark} label="Treasury &amp; Capital" testid="quick-finance" />
            <QuickLink to="/reports" Icon={FileText} label="Reports &amp; Exports" testid="quick-reports" />
            <QuickLink to="/audit-log" Icon={ShieldCheck} label="Audit Log" testid="quick-audit" />
            <QuickLink to="/settings" Icon={Server} label="Settings &amp; Backups" testid="quick-settings" />
          </div>
        </Card>
      </div>
    </section>
  );
}
