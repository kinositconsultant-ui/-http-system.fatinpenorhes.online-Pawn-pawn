import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { toast } from "sonner";
import {
  Users, FileText, DollarSign, Package,
  Warehouse as WarehouseIcon, Building2, Wallet, Percent,
  AlertOctagon, CheckCircle2, Gavel, Wrench, TrendingUp,
  AlertTriangle, Bell, RefreshCcw, Phone, Mail, Clock,
  Radio, Landmark, Activity, HandCoins, Star,
} from "lucide-react";

const fmt0 = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 0,
  }).format(Number(n || 0));

const REFRESH_MS = 60000;
const FEED_MAX = 10;

// Central event → display metadata. Toasts and the Live Activity Feed both
// pull from here so wording + icons stay in sync.
const EVENT_META = {
  "payment.created": {
    Icon: HandCoins,
    tone: "text-emerald-700",
    bg: "bg-emerald-50",
    kind: "success",
    title: "Payment recorded",
    desc: (p) => (p.amount != null ? `${fmt0(p.amount)} received` : "New payment received"),
  },
  "contract.created": {
    Icon: FileText,
    tone: "text-[#1B2D5C]",
    bg: "bg-[#1B2D5C]/[0.06]",
    kind: "info",
    title: "New contract signed",
    desc: (p) => p.contract_number || "A new pawn contract was created",
  },
  "auction.sold": {
    Icon: Gavel,
    tone: "text-amber-800",
    bg: "bg-amber-50",
    kind: "success",
    title: "Auction sold",
    desc: (p) => (p.sold_price != null ? `${fmt0(p.sold_price)} realised` : "An auction item was sold"),
  },
  "expense.created": {
    Icon: AlertOctagon,
    tone: "text-rose-700",
    bg: "bg-rose-50",
    kind: "info",
    title: "Expense logged",
    desc: (p) => [p.category, p.amount != null ? fmt0(p.amount) : ""].filter(Boolean).join(" · "),
  },
  "funding_source.created": {
    Icon: Landmark,
    tone: "text-sky-800",
    bg: "bg-sky-50",
    kind: "info",
    title: "Capital source added",
    desc: () => "New funding source recorded",
  },
  "funding_repayment.created": {
    Icon: Landmark,
    tone: "text-sky-800",
    bg: "bg-sky-50",
    kind: "success",
    title: "Capital repayment",
    desc: (p) => (p.total != null ? `${fmt0(p.total)} repaid` : "Repayment recorded"),
  },
  "inspection.reimbursed": {
    Icon: Wrench,
    tone: "text-stone-800",
    bg: "bg-stone-100",
    kind: "success",
    title: "Inspection reimbursed",
    desc: (p) => (p.amount != null ? `${fmt0(p.amount)} recovered` : "Inspection cost reimbursed"),
  },
};

// Fire the mapped toast for a WS event.
function toastForEvent(msg) {
  const meta = EVENT_META[msg.kind];
  if (!meta) return;
  const fn = meta.kind === "success" ? toast.success : toast.info;
  fn(meta.title, { description: meta.desc(msg.payload || {}), duration: 4000 });
}

// Build the WS URL from REACT_APP_BACKEND_URL (http[s] → ws[s]).
function wsUrl() {
  const base = process.env.REACT_APP_BACKEND_URL || "";
  const proto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  return `${proto}://${host}/api/ws/dashboard`;
}

export default function BusinessDashboard() {
  useLang();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [live, setLive] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const [events, setEvents] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const refetchDebounce = useRef(null);
  // Suppress duplicate toasts of the same kind within 1500ms (bursts of the
  // same event from a bulk action shouldn't spam the user).
  const lastToastAt = useRef({});
  // Skip toasts on the first ~1s after page load so a fresh mount doesn't
  // replay every queued event.
  const suppressUntil = useRef(Date.now() + 1500);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: r } = await api.get("/business/dashboard");
      setData(r);
      setLastRefresh(new Date());
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced refetch — many events in a short burst → single reload.
  const scheduleRefetch = useCallback(() => {
    if (refetchDebounce.current) clearTimeout(refetchDebounce.current);
    refetchDebounce.current = setTimeout(() => load(), 400);
  }, [load]);

  // WebSocket lifecycle — reconnect with backoff on drop.
  useEffect(() => {
    let closed = false;

    function open() {
      try {
        const ws = new WebSocket(wsUrl());
        wsRef.current = ws;
        ws.onopen = () => setLive(true);
        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data);
            if (msg.kind && msg.kind !== "connected") {
              setLastEvent(msg);
              scheduleRefetch();
              // Append to the Live Activity Feed (newest first, capped)
              setEvents((prev) => [
                { ...msg, receivedAt: Date.now() },
                ...prev,
              ].slice(0, FEED_MAX));
              // Fire a toast (with per-kind debounce + startup grace window)
              const now = Date.now();
              if (now >= suppressUntil.current) {
                const last = lastToastAt.current[msg.kind] || 0;
                if (now - last > 1500) {
                  lastToastAt.current[msg.kind] = now;
                  toastForEvent(msg);
                }
              }
            }
          } catch { /* ignore non-JSON */ }
        };
        ws.onclose = () => {
          setLive(false);
          wsRef.current = null;
          if (!closed) {
            reconnectTimer.current = setTimeout(open, 3000);
          }
        };
        ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
      } catch {
        setLive(false);
        if (!closed) reconnectTimer.current = setTimeout(open, 5000);
      }
    }

    open();
    return () => {
      closed = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (refetchDebounce.current) clearTimeout(refetchDebounce.current);
      if (wsRef.current) { try { wsRef.current.close(); } catch { /* noop */ } }
    };
  }, [scheduleRefetch]);

  useEffect(() => {
    load();
    const iv = setInterval(() => { if (!document.hidden) load(); }, REFRESH_MS);
    return () => clearInterval(iv);
  }, [load]);

  const monthLabel = data
    ? new Date(data.month_from).toLocaleString("en-US", { month: "long", year: "numeric" })
    : "";

  return (
    <div className="space-y-6" data-testid="business-dashboard-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">Executive Overview</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
            Business Dashboard
          </h1>
          <p className="text-sm text-stone-600 mt-1 flex items-center gap-2 flex-wrap">
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${
                live
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-stone-100 text-stone-600 border-stone-200"
              }`}
              data-testid="ws-status-pill"
              title={live ? "Live push connected" : "Push disconnected — falling back to 60s polling"}
            >
              <Radio className={`w-3 h-3 ${live ? "animate-pulse" : ""}`} />
              {live ? "Live" : "Polling"}
            </span>
            <span>Auto-refreshes every 60 seconds</span>
            {lastRefresh && (
              <span className="text-stone-400">
                · updated {lastRefresh.toLocaleTimeString()}
              </span>
            )}
            {lastEvent && (
              <span className="text-stone-400" data-testid="ws-last-event">
                · last event: {lastEvent.kind}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-stone-300 bg-white hover:bg-stone-50 text-sm disabled:opacity-40"
          data-testid="refresh-btn"
        >
          <RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </header>

      <SectionTitle>Portfolio Snapshot</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
        <Tile Icon={Users} label="Active Clients" value={data?.active_clients} tone="text-[#1B2D5C]" bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25" testid="k-clients" />
        <Tile Icon={FileText} label="Active Contracts" value={data?.active_contracts} tone="text-[#1B2D5C]" bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25" testid="k-contracts" />
        <Tile Icon={DollarSign} label="Active Loans" value={fmt0(data?.total_principal_remaining)} hint={data ? `original ${fmt0(data.total_loan_amount)}` : ""} tone="text-sky-800" bg="bg-sky-50 border-sky-200" testid="k-loans" />
        <Tile Icon={Package} label="Active Pledged Value" value={fmt0(data?.active_items_market_value)} hint={data ? `${data.active_items_count} items` : ""} tone="text-emerald-800" bg="bg-emerald-50 border-emerald-200" testid="k-pledged" />
        <Tile Icon={Wallet} label="Cash on Hand" value={fmt0(data?.cash_on_hand)} tone={Number(data?.cash_on_hand || 0) >= 0 ? "text-emerald-700" : "text-rose-700"} bg="bg-stone-50 border-stone-300" testid="k-cash" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Tile Icon={WarehouseIcon} label="Warehouse Items (Active)" value={data?.warehouse_items_count} tone="text-[#1B2D5C]" bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25" testid="k-warehouse" />
        <Tile Icon={Building2} label="Office Items (Active)" value={data?.office_items_count} tone="text-emerald-800" bg="bg-emerald-50 border-emerald-200" testid="k-office" />
      </div>

      <SectionTitle>This Month · {monthLabel}</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Tile Icon={Percent} label="Interest Received" value={fmt0(data?.month_interest_received)} tone="text-sky-800" bg="bg-sky-50 border-sky-200" testid="m-interest" />
        <Tile Icon={AlertOctagon} label="Penalties Received" value={fmt0(data?.month_penalty_received)} tone="text-rose-800" bg="bg-rose-50 border-rose-200" testid="m-penalty" />
        <Tile Icon={CheckCircle2} label="Full Payments" value={fmt0(data?.month_full_payments_total)} hint={data ? `${data.month_full_payments_count} contracts closed` : ""} tone="text-emerald-800" bg="bg-emerald-50 border-emerald-200" testid="m-fullpay" />
        <Tile Icon={Gavel} label="Auctions Held" value={data?.month_auctions_count} hint={data ? fmt0(data.month_auctions_total) : ""} tone="text-amber-800" bg="bg-amber-50 border-amber-200" testid="m-auctions" />
        <Tile Icon={Wrench} label="Inspections Reimbursed" value={fmt0(data?.month_inspections_reimbursed)} tone="text-stone-800" bg="bg-stone-50 border-stone-300" testid="m-reimb" />
        <Tile Icon={TrendingUp} label="Auction Profit (lifetime)" value={fmt0(data?.auction_profit_lifetime)} tone="text-amber-800" bg="bg-amber-50 border-amber-200" testid="m-aucprofit" />
      </div>

      <SectionTitle>Company Profit</SectionTitle>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Tile Icon={TrendingUp} label="Gross Profit (lifetime)" value={fmt0(data?.gross_profit_lifetime)} hint="Interest + Penalty + Auction" tone="text-[#1B2D5C]" bg="bg-[#1B2D5C]/[0.06] border-[#1B2D5C]/25" testid="p-gross" />
        <Tile Icon={TrendingUp} label="Auction Profit (lifetime)" value={fmt0(data?.auction_profit_lifetime)} tone="text-amber-800" bg="bg-amber-50 border-amber-200" testid="p-auction" />
        <Tile Icon={TrendingUp} label="Net Profit (lifetime)" value={fmt0(data?.net_profit_lifetime)} hint="Gross − Expenses" tone={Number(data?.net_profit_lifetime || 0) >= 0 ? "text-emerald-700" : "text-rose-700"} bg="bg-emerald-50 border-emerald-200" testid="p-net" />
      </div>

      <SectionTitle>Contracts Expiring</SectionTitle>
      <div className="grid grid-cols-3 gap-3">
        <ExpiringTile days="7 days" count={data?.expiring_7_count} rows={data?.expiring_7} tone="border-rose-300 bg-rose-50" text="text-rose-800" testid="exp-7" />
        <ExpiringTile days="15 days" count={data?.expiring_15_count} rows={data?.expiring_15} tone="border-amber-300 bg-amber-50" text="text-amber-800" testid="exp-15" />
        <ExpiringTile days="Month 2" count={data?.expiring_month2_count} rows={data?.expiring_month2} tone="border-orange-300 bg-orange-50" text="text-orange-800" testid="exp-m2" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <NotificationPanel
          Icon={Bell}
          title="Expiring in 7 Days · Contact These Clients"
          rows={data?.expiring_7 || []}
          empty="No contracts due in the next 7 days."
          testid="notif-expiring"
        />
        <UpcomingLoansPanel loans={data?.upcoming_loan_repayments || []} />
        <LiveActivityFeed events={events} live={live} />
      </div>
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <div className="text-eyebrow flex items-center gap-2">
      <span className="w-8 h-px bg-[#1B2D5C]/40" />
      {children}
    </div>
  );
}

function Tile({ Icon, label, value, hint, tone, bg, testid }) {
  return (
    <div className={`rounded-lg border ${bg} p-3 md:p-4`} data-testid={testid}>
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`w-4 h-4 ${tone}`} />}
        <span className="text-[11px] uppercase tracking-wide text-stone-500">{label}</span>
      </div>
      <div className={`font-display text-lg md:text-2xl font-semibold mt-1 ${tone}`}>
        {value ?? "…"}
      </div>
      {hint && <div className="text-[11px] text-stone-500 mt-0.5">{hint}</div>}
    </div>
  );
}

function ExpiringTile({ days, count, rows, tone, text, testid }) {
  return (
    <Card className={`p-3 md:p-4 border ${tone}`} data-testid={testid}>
      <div className="flex items-center gap-2">
        <AlertTriangle className={`w-4 h-4 ${text}`} />
        <span className="text-[11px] uppercase tracking-wide text-stone-500">
          Due within {days}
        </span>
      </div>
      <div className={`font-display text-2xl md:text-3xl font-semibold mt-1 ${text}`}>
        {count ?? "…"}
      </div>
      <div className="text-[11px] text-stone-600 mt-0.5">
        {rows && rows.length > 0
          ? `first: ${rows[0].contract_number} · ${rows[0].due_date}`
          : "no upcoming"}
      </div>
    </Card>
  );
}

function NotificationPanel({ Icon, title, rows, empty, testid }) {
  return (
    <Card className="p-3 md:p-4 border border-stone-200 shadow-none rounded-lg bg-white" data-testid={testid}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-[#1B2D5C]" />
        <span className="text-sm font-semibold">{title}</span>
      </div>
      {rows.length === 0 ? (
        <div className="text-xs text-stone-400 py-4 text-center">{empty}</div>
      ) : (
        <div className="max-h-64 overflow-y-auto divide-y divide-stone-100">
          {rows.map((r) => (
            <div
              key={r.id}
              className={`py-2 flex items-center justify-between gap-2 text-xs ${
                r.is_vip ? "bg-amber-50/40 -mx-3 px-3 rounded" : ""
              }`}
              data-testid={r.is_vip ? `notif-vip-row-${r.id}` : undefined}
            >
              <div className="min-w-0">
                <div className="font-medium truncate flex items-center gap-1.5">
                  {r.is_vip && (
                    <span
                      className="inline-flex items-center gap-0.5 text-[9px] font-bold px-1 py-0 rounded-full bg-amber-500 text-white shrink-0"
                      title="VIP client"
                    >
                      <Star className="w-2 h-2 fill-current" />
                      VIP
                    </span>
                  )}
                  <span className="truncate">{r.client_name || "—"}</span>
                  <span className="font-mono text-[10px] text-stone-500 shrink-0">
                    {r.contract_number}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-0.5 text-[10px] text-stone-500">
                  {r.client_phone && (
                    <span className="inline-flex items-center gap-1">
                      <Phone className="w-3 h-3" /> {r.client_phone}
                    </span>
                  )}
                  {r.client_email && (
                    <span className="inline-flex items-center gap-1">
                      <Mail className="w-3 h-3" /> {r.client_email}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1">
                    <Clock className="w-3 h-3" /> due {r.due_date}
                  </span>
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-semibold tabular-nums">{fmt0(r.principal_remaining)}</div>
                <div className="text-[10px] text-stone-500">{r.item_type}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function UpcomingLoansPanel({ loans }) {
  return (
    <Card className="p-3 md:p-4 border border-stone-200 shadow-none rounded-lg bg-white" data-testid="notif-loans">
      <div className="flex items-center gap-2 mb-2">
        <Bell className="w-4 h-4 text-amber-700" />
        <span className="text-sm font-semibold">
          Company Loans · Upcoming Repayments (next 30 days)
        </span>
      </div>
      {loans.length === 0 ? (
        <div className="text-xs text-stone-400 py-4 text-center">
          No company loan repayments due in the next 30 days.
        </div>
      ) : (
        <div className="max-h-64 overflow-y-auto divide-y divide-stone-100">
          {loans.map((l) => (
            <div key={l.id} className="py-2 flex items-center justify-between gap-2 text-xs">
              <div>
                <div className="font-medium">{l.name}</div>
                <div className="text-[10px] text-stone-500">
                  {l.source_type} · due {l.due_date} ·
                  <span className={l.days_until_due <= 7 ? "text-rose-700 font-medium" : ""}>
                    {" "}{l.days_until_due} day(s)
                  </span>
                </div>
              </div>
              <div className="font-semibold tabular-nums text-rose-800">
                {fmt0(l.outstanding)}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// Relative-time formatter — no library, works well for the last 24h window
// of live events.
function relTime(ts) {
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function LiveActivityFeed({ events, live }) {
  // Tick every 30s so relative timestamps stay fresh even when no new event arrives.
  const [, force] = useState(0);
  useEffect(() => {
    const iv = setInterval(() => force((n) => n + 1), 30000);
    return () => clearInterval(iv);
  }, []);

  return (
    <Card
      className="p-3 md:p-4 border border-stone-200 shadow-none rounded-lg bg-white"
      data-testid="live-activity-feed"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Activity className={`w-4 h-4 ${live ? "text-emerald-700" : "text-stone-400"}`} />
          <span className="text-sm font-semibold">Live Activity</span>
        </div>
        <span
          className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ${
            live ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"
          }`}
        >
          {events.length}/{FEED_MAX}
        </span>
      </div>
      {events.length === 0 ? (
        <div className="text-xs text-stone-400 py-6 text-center">
          Waiting for the first live event…
        </div>
      ) : (
        <div className="max-h-64 overflow-y-auto divide-y divide-stone-100">
          {events.map((e, idx) => {
            const meta = EVENT_META[e.kind];
            const Icon = meta?.Icon || Activity;
            return (
              <div
                key={`${e.receivedAt}-${idx}`}
                className="py-2 flex items-center gap-2 text-xs"
                data-testid={`live-feed-row-${idx}`}
              >
                <div className={`p-1.5 rounded ${meta?.bg || "bg-stone-100"}`}>
                  <Icon className={`w-3.5 h-3.5 ${meta?.tone || "text-stone-600"}`} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{meta?.title || e.kind}</div>
                  <div className="text-[10px] text-stone-500 truncate">
                    {meta ? meta.desc(e.payload || {}) : ""}
                  </div>
                </div>
                <div className="text-[10px] text-stone-400 shrink-0 tabular-nums">
                  {relTime(e.receivedAt)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
