import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { CalendarClock, Sparkles } from "lucide-react";

const usd = (n) => `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Payments dialog: "pay today" vs "pay next month" so staff can show the client what waiting costs.
export default function RedemptionQuote({ contractId }) {
  const [q, setQ] = useState(null);
  useEffect(() => {
    if (!contractId) return undefined;
    let alive = true;
    setQ(null);
    api.get(`/contracts/${contractId}/redemption-quote`).then((r) => alive && setQ(r.data)).catch(() => {});
    return () => { alive = false; };
  }, [contractId]);
  if (!contractId || !q || q.status === "redeemed") return null;
  return (
    <div className="rounded-lg border border-[#1B2D5C]/15 bg-[#1B2D5C]/[0.03] p-3" data-testid="redemption-quote">
      <div className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold mb-2 inline-flex items-center gap-1">
        <CalendarClock className="w-3.5 h-3.5" /> Early redemption quote
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-md bg-white border border-emerald-200 p-2.5">
          <div className="text-[10px] uppercase tracking-wider text-emerald-800">Pay today</div>
          <div className="font-display text-xl text-emerald-800" data-testid="quote-today">{usd(q.today.total)}</div>
          <div className="text-[10px] text-stone-500">principal {usd(q.today.principal)} · interest {usd(q.today.interest)}{q.today.penalty > 0 ? ` · penalty ${usd(q.today.penalty)}` : ""}</div>
        </div>
        <div className="rounded-md bg-white border border-stone-200 p-2.5">
          <div className="text-[10px] uppercase tracking-wider text-stone-500">Pay next month</div>
          <div className="font-display text-xl text-stone-800" data-testid="quote-next-month">{usd(q.next_month.total)}</div>
          <div className="text-[10px] text-stone-500">
            {q.next_month.capped ? "2-month cap reached — no extra interest" : `+ interest ${usd(q.next_month.extra_interest)}`}
            {q.next_month.extra_penalty > 0 ? ` · + penalty ${usd(q.next_month.extra_penalty)}` : ""}
          </div>
        </div>
      </div>
      {q.saving > 0 && (
        <div className="mt-2 text-xs text-emerald-800 inline-flex items-center gap-1" data-testid="quote-saving">
          <Sparkles className="w-3.5 h-3.5" /> Paying today saves the client {usd(q.saving)}
        </div>
      )}
    </div>
  );
}
