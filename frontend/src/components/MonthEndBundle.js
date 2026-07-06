import { useEffect, useMemo, useState } from "react";
import { api, API_BASE } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Package, Download, Clock, RefreshCw } from "lucide-react";

const MONTHS = [
  ["01", "January"], ["02", "February"], ["03", "March"], ["04", "April"],
  ["05", "May"], ["06", "June"], ["07", "July"], ["08", "August"],
  ["09", "September"], ["10", "October"], ["11", "November"], ["12", "December"],
];

const fmtBytes = (n) => {
  if (!n && n !== 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
};

const fmtDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

export default function MonthEndBundle() {
  const { t } = useLang();
  // Default = previous full month
  const now = new Date();
  const defaultMonth = now.getMonth() === 0 ? 12 : now.getMonth();
  const defaultYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
  const [month, setMonth] = useState(String(defaultMonth).padStart(2, "0"));
  const [year, setYear] = useState(String(defaultYear));
  const [archives, setArchives] = useState([]);
  const [schedule, setSchedule] = useState(null);
  const [loading, setLoading] = useState(false);

  const yearOpts = useMemo(() => {
    const y = now.getFullYear();
    return [String(y - 2), String(y - 1), String(y), String(y + 1)];
  }, [now]);

  const loadArchives = async () => {
    try {
      const { data } = await api.get("/monthend/archives");
      setArchives(data || []);
    } catch {
      setArchives([]);
    }
  };

  const loadSchedule = async () => {
    try {
      const { data } = await api.get("/admin/backups/schedule");
      setSchedule(data);
    } catch {
      setSchedule(null);
    }
  };

  useEffect(() => {
    loadArchives();
    loadSchedule();
  }, []);

  const generate = async () => {
    setLoading(true);
    try {
      const url = `${API_BASE}/monthend/generate?month=${year}-${month}`;
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const dlUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = dlUrl;
      a.download = `monthend-${year}-${month}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(dlUrl);
      await loadArchives();
    } catch (e) {
      alert(`Failed: ${e.message || e}`);
    }
    setLoading(false);
  };

  const downloadArchive = (name) => {
    const url = `${API_BASE}/monthend/archives/${encodeURIComponent(name)}`;
    // Same-origin cookie-authed download
    window.open(url, "_blank");
  };

  return (
    <Card
      className="p-4 md:p-6 border border-stone-200 shadow-none rounded-lg bg-white print:hidden"
      data-testid="monthend-bundle-card"
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-md bg-[#1B2D5C]/10 text-[#1B2D5C] flex items-center justify-center shrink-0">
          <Package className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <div className="text-eyebrow">{t("reports")}</div>
          <h2 className="font-display text-lg md:text-xl font-semibold mt-1 text-stone-900">
            {t("monthend_bundle")}
          </h2>
          <p className="text-sm text-stone-600 mt-1 max-w-3xl">{t("monthend_desc")}</p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("month")}</div>
          <Select value={month} onValueChange={setMonth}>
            <SelectTrigger className="w-40" data-testid="monthend-month">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MONTHS.map(([v, label]) => (
                <SelectItem key={v} value={v}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("year")}</div>
          <Select value={year} onValueChange={setYear}>
            <SelectTrigger className="w-32" data-testid="monthend-year">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {yearOpts.map((y) => (
                <SelectItem key={y} value={y}>{y}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          onClick={generate}
          disabled={loading}
          className="bg-[#1B2D5C] hover:bg-[#0F1B3A] text-white"
          data-testid="monthend-generate"
        >
          <Download className="w-4 h-4 mr-1" />
          {loading ? "…" : t("generate_bundle")}
        </Button>
        <Button
          variant="outline"
          onClick={() => { loadArchives(); loadSchedule(); }}
          data-testid="monthend-refresh"
        >
          <RefreshCw className="w-4 h-4 mr-1" />
          {t("reset")}
        </Button>

        {schedule?.next_monthend_run_at && (
          <div className="ml-auto flex items-center gap-1.5 text-xs text-stone-500" data-testid="monthend-next-run">
            <Clock className="w-3.5 h-3.5" />
            <span>{t("next_auto_run")}: {fmtDate(schedule.next_monthend_run_at)}</span>
          </div>
        )}
      </div>

      {/* Archives list */}
      <div className="mt-6 border-t border-stone-200 pt-4">
        <div className="text-eyebrow mb-2">{t("monthend_archives")}</div>
        {archives.length === 0 ? (
          <div className="text-sm text-stone-500 py-3">No archives yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="monthend-archive-table">
              <thead className="bg-stone-50 text-left">
                <tr>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">{t("month")}</th>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">File</th>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">{t("file_size")}</th>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold">{t("modified")}</th>
                  <th className="px-3 py-2 text-[10px] uppercase tracking-wider text-stone-500 font-semibold text-right">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {archives.map((a) => (
                  <tr key={a.name} className="border-t border-stone-100 hover:bg-stone-50/50">
                    <td className="px-3 py-2 whitespace-nowrap font-medium">{a.month || "—"}</td>
                    <td className="px-3 py-2 whitespace-nowrap font-mono text-xs text-stone-600">{a.name}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{fmtBytes(a.size)}</td>
                    <td className="px-3 py-2 whitespace-nowrap text-stone-500">{fmtDate(a.modified)}</td>
                    <td className="px-3 py-2 whitespace-nowrap text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => downloadArchive(a.name)}
                        data-testid={`monthend-download-${a.month}`}
                      >
                        <Download className="w-3.5 h-3.5 mr-1" />
                        {t("download")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  );
}
