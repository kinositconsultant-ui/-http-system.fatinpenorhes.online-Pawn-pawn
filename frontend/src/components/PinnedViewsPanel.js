import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "./ui/card";
import { Pin, ArrowUpRight, Loader2 } from "lucide-react";

// Same money-column set the Reports page uses — keep in sync.
const MONEY_KEYS = new Set([
  "loan_amount", "interest_amount", "amount", "paid_amount", "principal_remaining",
  "interest_remaining", "penalty", "market_value", "starting_price", "sold_price",
  "total_loan", "total_payments", "interest_received", "total_penalty",
  "total_outstanding", "total_interest", "total_amount", "profit",
]);

const fmtVal = (col, v) => {
  if (v == null || v === "") return "—";
  if (MONEY_KEYS.has(col)) {
    const n = typeof v === "number" ? v : parseFloat(v);
    if (!Number.isNaN(n)) return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return String(v);
};

const prettify = (s) => (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function buildQuery(filters) {
  const params = new URLSearchParams();
  Object.entries(filters || {}).forEach(([k, v]) => { if (v) params.set(k, v); });
  const q = params.toString();
  return q ? `?${q}` : "";
}

function PinnedCard({ view }) {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const q = buildQuery(view.filters);
        const { data: d } = await api.get(`/reports/v2/${view.tab}${q}`);
        if (alive) setData(d);
      } catch {
        if (alive) setData(null);
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [view.tab, JSON.stringify(view.filters || {})]);

  const rows = (data?.rows || []).slice(0, 5);
  const cols = (data?.columns || []).slice(0, 3);
  const totalRows = data?.rows?.length ?? 0;
  const threshold = view.alert_threshold;
  const alerting = threshold != null && totalRows > threshold;
  // Pull the first numeric-looking KPI for headline
  const kpiEntries = Object.entries(data?.kpis || {})
    .filter(([_, v]) => !(typeof v === "object" && v !== null));

  const open = () => {
    // Pass a hint via sessionStorage so Reports can auto-apply the view.
    try {
      sessionStorage.setItem("pending-report-view", JSON.stringify({
        tab: view.tab, filters: view.filters || {}, sort: view.sort || null,
      }));
    } catch { /* sessionStorage unavailable */ }
    navigate("/reports");
  };

  return (
    <Card
      className={`p-4 md:p-5 border shadow-none rounded-lg bg-white flex flex-col transition ${
        alerting ? "border-red-300 ring-1 ring-red-200" : "border-stone-200"
      }`}
      data-testid={`pinned-view-card-${view.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            {alerting ? (
              <span
                className="relative inline-flex w-2 h-2"
                data-testid={`pinned-view-alert-${view.id}`}
                title={`Row count ${totalRows} exceeds threshold ${threshold}`}
              >
                <span className="absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75 animate-ping"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-600"></span>
              </span>
            ) : (
              <Pin className="w-3.5 h-3.5 text-[#1B2D5C] fill-[#1B2D5C]" />
            )}
            <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500 font-semibold truncate">
              {view.tab.replace("-", " ")}
            </div>
          </div>
          <div className="font-display text-lg mt-1 text-stone-900 truncate" title={view.name}>
            {view.name}
          </div>
        </div>
        <button
          onClick={open}
          className="shrink-0 text-stone-400 hover:text-[#1B2D5C] p-1 rounded"
          title={t("apply_view")}
          data-testid={`pinned-view-open-${view.id}`}
        >
          <ArrowUpRight className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-stone-500 mt-4">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…
        </div>
      ) : (
        <>
          <div className="mt-3 flex items-baseline gap-2">
            <div className={`font-display text-3xl font-semibold ${alerting ? "text-red-600" : "text-stone-900"}`}>
              {totalRows}
            </div>
            <div className="text-xs text-stone-500">rows</div>
            {threshold != null && (
              <div className={`text-[10px] ${alerting ? "text-red-600 font-semibold" : "text-stone-400"}`}>
                / alert &gt; {threshold}
              </div>
            )}
            {kpiEntries.slice(0, 1).map(([k, v]) => (
              <div key={k} className="ml-3 text-xs text-stone-500">
                · {prettify(k)}: <span className="text-stone-800 font-medium">
                  {MONEY_KEYS.has(k) ? fmtVal(k, v) : String(v)}
                </span>
              </div>
            ))}
          </div>
          {rows.length > 0 && cols.length > 0 && (
            <div className="mt-3 border-t border-stone-100 pt-2">
              <table className="w-full text-[11px]">
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className="border-b border-stone-50 last:border-0">
                      {cols.map((c) => (
                        <td key={c} className="py-1 pr-2 truncate text-stone-700 max-w-[140px]">
                          {fmtVal(c, r[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <button
        onClick={open}
        className="mt-auto pt-3 text-xs text-[#1B2D5C] hover:underline underline-offset-2 text-left"
        data-testid={`pinned-view-openlink-${view.id}`}
      >
        {t("apply_view")} →
      </button>
    </Card>
  );
}

export default function PinnedViewsPanel() {
  const { t } = useLang();
  const [pinned, setPinned] = useState([]);
  const [nextDigest, setNextDigest] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/report-views");
        setPinned((data || []).filter((v) => v.pinned));
      } catch {
        setPinned([]);
      }
      try {
        const { data: sched } = await api.get("/admin/backups/schedule");
        setNextDigest(sched?.next_alert_digest_run_at || null);
      } catch { /* non-admins can't see the schedule — that's fine */ }
    })();
  }, []);

  if (pinned.length === 0) return null;

  const hasAlert = pinned.some((v) => v.alert_threshold != null);

  return (
    <section data-testid="pinned-views-panel">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Pin className="w-4 h-4 text-[#1B2D5C]" />
          <div className="text-eyebrow">{t("pinned_views")}</div>
        </div>
        {hasAlert && nextDigest && (
          <div
            className="text-[10px] text-stone-500 flex items-center gap-1"
            data-testid="pinned-views-next-digest"
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Daily alert digest · next run {new Date(nextDigest).toLocaleString()}
          </div>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
        {pinned.map((v) => (
          <PinnedCard key={v.id} view={v} />
        ))}
      </div>
    </section>
  );
}
