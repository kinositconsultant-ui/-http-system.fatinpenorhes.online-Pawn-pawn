import { Check, CheckCheck, Clock, XCircle } from "lucide-react";

/**
 * WhatsAppStatusPill — compact delivery-status badge for reminder messages.
 * Status vocabulary matches Meta's message.status callback:
 *   queued    — logged locally, not yet sent to Meta
 *   mocked    — WhatsApp not configured, message was mocked
 *   sent      — accepted by Meta Cloud API
 *   delivered — device received it
 *   read      — recipient opened it
 *   failed    — Meta returned an error
 * Anything null / undefined renders as a neutral "no reminder" hint so the
 * caller doesn't have to conditionally render.
 */
export default function WhatsAppStatusPill({ status, compact = true, className = "" }) {
  if (!status) {
    return (
      <span
        className={`inline-flex items-center gap-1 text-[10px] text-stone-400 ${className}`}
        data-testid="wa-pill-none"
      >
        <Clock className="w-3 h-3" /> no reminder
      </span>
    );
  }
  const map = {
    queued: {
      cls: "bg-stone-100 text-stone-700 border-stone-300",
      Icon: Clock,
      label: "queued",
    },
    mocked: {
      cls: "bg-stone-100 text-stone-500 border-stone-300",
      Icon: Clock,
      label: "mocked",
    },
    sent: {
      cls: "bg-sky-100 text-sky-800 border-sky-300",
      Icon: Check,
      label: "sent",
    },
    delivered: {
      cls: "bg-amber-100 text-amber-800 border-amber-300",
      Icon: CheckCheck,
      label: "delivered",
    },
    read: {
      cls: "bg-emerald-100 text-emerald-800 border-emerald-400",
      Icon: CheckCheck,
      label: "read",
    },
    failed: {
      cls: "bg-rose-100 text-rose-800 border-rose-300",
      Icon: XCircle,
      label: "failed",
    },
    error: {
      cls: "bg-rose-100 text-rose-800 border-rose-300",
      Icon: XCircle,
      label: "failed",
    },
  };
  const cfg = map[status] || map.queued;
  const Icon = cfg.Icon;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border ${cfg.cls} ${
        compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-xs"
      } ${className}`}
      title={`WhatsApp reminder ${cfg.label}`}
      data-testid={`wa-pill-${cfg.label}`}
    >
      <Icon className="w-3 h-3" />
      {cfg.label}
    </span>
  );
}
