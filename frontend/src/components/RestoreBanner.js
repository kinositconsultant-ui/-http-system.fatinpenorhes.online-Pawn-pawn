import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { RefreshCw, X, DatabaseBackup } from "lucide-react";

// Timestamp of when this app instance loaded — any restore AFTER this moment
// means the data on screen is stale.
const LOADED_AT = Date.now();
const POLL_MS = 30000;

export const RestoreBanner = () => {
  const [info, setInfo] = useState(null);
  const [dismissedAt, setDismissedAt] = useState(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const { data } = await api.get("/system/status");
        if (alive) setInfo(data);
      } catch { /* non-fatal */ }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const restoreTs = info?.last_restore_at ? new Date(info.last_restore_at).getTime() : 0;
  const show = restoreTs > LOADED_AT && restoreTs !== dismissedAt;
  if (!show) return null;

  return (
    <div
      className="fixed top-0 md:top-0 inset-x-0 z-[60] bg-amber-500 text-stone-900 shadow-lg"
      data-testid="restore-banner"
    >
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center gap-3 flex-wrap">
        <DatabaseBackup className="w-5 h-5 shrink-0" />
        <div className="text-sm font-semibold flex-1 min-w-[200px]">
          A system restore just completed
          {info?.restored_by ? ` (by ${info.restored_by})` : ""} — the data on your
          screen may be outdated.
        </div>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-stone-900 text-white text-xs font-bold hover:bg-stone-700 transition-colors"
          data-testid="restore-banner-refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh now
        </button>
        <button
          type="button"
          onClick={() => setDismissedAt(restoreTs)}
          className="p-1.5 rounded-full hover:bg-amber-600/40 transition-colors"
          aria-label="Dismiss"
          data-testid="restore-banner-dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
