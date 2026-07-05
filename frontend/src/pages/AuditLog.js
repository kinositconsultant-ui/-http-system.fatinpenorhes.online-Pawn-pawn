import { useEffect, useState, useCallback } from "react";
import { api, API_BASE } from "../lib/api";
import { useLang } from "../context/LangContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { FileDown, FileText, RotateCcw, Filter } from "lucide-react";
import { toast } from "sonner";

const RESOURCE_OPTIONS = [
  "",
  "contract",
  "payment",
  "auction",
  "client",
  "user",
  "settings",
  "system",
  "reminders",
];

const ACTION_OPTIONS = [
  "",
  "create",
  "update",
  "delete",
  "backup",
  "backup_project",
  "reactivate",
  "move_to_auction",
  "mark_sold",
  "issue_card",
  "renew_card",
  "revoke_card",
  "whatsapp_send",
  "whatsapp_adhoc_send",
  "run_reminders",
];

export default function AuditLog() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    resource: "",
    action: "",
    actor_email: "",
    date_from: "",
    date_to: "",
    limit: 200,
  });

  const buildQuery = useCallback(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) params.set(k, String(v));
    });
    return params.toString();
  }, [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = buildQuery();
      const { data } = await api.get(`/audit-log${q ? "?" + q : ""}`);
      setRows(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load audit log");
    } finally {
      setLoading(false);
    }
  }, [buildQuery]);

  useEffect(() => {
    load();
  }, [load]);

  const reset = () => {
    setFilters({
      resource: "",
      action: "",
      actor_email: "",
      date_from: "",
      date_to: "",
      limit: 200,
    });
  };

  const exportCsv = async () => {
    const q = buildQuery();
    try {
      const res = await api.get(`/audit-log/export/csv?${q}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) {
      toast.error(e.response?.data?.detail || "CSV export failed");
    }
  };

  const exportPdf = async () => {
    const q = buildQuery();
    try {
      const res = await api.get(`/audit-log/export/pdf?${q}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      toast.error(e.response?.data?.detail || "PDF export failed");
    }
  };

  const formatDetails = (d) => {
    if (!d || (typeof d === "object" && Object.keys(d).length === 0)) return "—";
    if (typeof d === "string") return d;
    return Object.entries(d)
      .slice(0, 4)
      .map(([k, v]) => `${k}=${typeof v === "object" ? "…" : String(v).slice(0, 40)}`)
      .join(", ");
  };

  return (
    <div className="space-y-6" data-testid="audit-log-root">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-eyebrow">{t("audit_log")}</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">
            {t("audit_log")}
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            {rows.length} entries — filter + export as CSV or PDF for compliance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={exportCsv}
            data-testid="audit-export-csv"
            className="text-emerald-800 border-emerald-300 hover:bg-emerald-50"
          >
            <FileDown className="w-4 h-4 mr-1.5" /> CSV
          </Button>
          <Button
            variant="outline"
            onClick={exportPdf}
            data-testid="audit-export-pdf"
            className="text-red-800 border-red-300 hover:bg-red-50"
          >
            <FileText className="w-4 h-4 mr-1.5" /> PDF
          </Button>
        </div>
      </header>

      {/* Filter Bar */}
      <div className="rounded-lg border border-stone-200 bg-white p-4 space-y-3" data-testid="audit-filter-bar">
        <div className="flex items-center gap-2 text-stone-700">
          <Filter className="w-4 h-4" />
          <span className="text-sm font-semibold">Filters</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <FilterField label="Resource">
            <Select
              value={filters.resource || "__all"}
              onValueChange={(v) => setFilters({ ...filters, resource: v === "__all" ? "" : v })}
            >
              <SelectTrigger data-testid="audit-filter-resource">
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all">Any</SelectItem>
                {RESOURCE_OPTIONS.filter(Boolean).map((r) => (
                  <SelectItem key={r} value={r}>{r}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Action">
            <Select
              value={filters.action || "__all"}
              onValueChange={(v) => setFilters({ ...filters, action: v === "__all" ? "" : v })}
            >
              <SelectTrigger data-testid="audit-filter-action">
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all">Any</SelectItem>
                {ACTION_OPTIONS.filter(Boolean).map((a) => (
                  <SelectItem key={a} value={a}>{a}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FilterField>
          <FilterField label="Actor email contains">
            <Input
              value={filters.actor_email}
              onChange={(e) => setFilters({ ...filters, actor_email: e.target.value })}
              placeholder="admin@..."
              data-testid="audit-filter-actor"
            />
          </FilterField>
          <FilterField label="From">
            <Input
              type="date"
              value={filters.date_from}
              onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
              data-testid="audit-filter-from"
            />
          </FilterField>
          <FilterField label="To">
            <Input
              type="date"
              value={filters.date_to}
              onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
              data-testid="audit-filter-to"
            />
          </FilterField>
          <FilterField label="Limit">
            <Input
              type="number"
              value={filters.limit}
              min={1}
              max={2000}
              onChange={(e) => setFilters({ ...filters, limit: Number(e.target.value) || 200 })}
              data-testid="audit-filter-limit"
            />
          </FilterField>
        </div>
        <div className="flex gap-2 justify-end">
          <Button
            variant="ghost"
            onClick={reset}
            data-testid="audit-filter-reset"
          >
            <RotateCcw className="w-4 h-4 mr-1.5" /> Reset
          </Button>
          <Button
            onClick={load}
            className="bg-[#1B2D5C] hover:bg-[#0F1B3A]"
            disabled={loading}
            data-testid="audit-filter-apply"
          >
            <Filter className="w-4 h-4 mr-1.5" /> {loading ? "Loading…" : "Apply"}
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="audit-log-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>When (UTC)</Th>
              <Th>Actor</Th>
              <Th>Action</Th>
              <Th>Resource</Th>
              <Th>ID</Th>
              <Th>Details</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100 align-top hover:bg-stone-50/60">
                <Td className="whitespace-nowrap text-xs">
                  {(r.created_at || "").slice(0, 19).replace("T", " ")}
                </Td>
                <Td className="whitespace-nowrap text-xs">{r.actor_email || "—"}</Td>
                <Td>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200 font-medium">
                    {r.action}
                  </span>
                </Td>
                <Td className="text-xs">{r.resource || "—"}</Td>
                <Td className="text-xs text-stone-500 font-mono">
                  {(r.resource_id || "").slice(0, 8)}
                </Td>
                <Td className="text-xs text-stone-600 max-w-md break-words">
                  {formatDetails(r.details || r.payload)}
                </Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="p-8 text-center text-stone-500" colSpan={6}>
                  {loading ? "Loading…" : "No log entries match these filters."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilterField({ label, children }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs uppercase tracking-wider text-stone-500">{label}</Label>
      {children}
    </div>
  );
}

function Th({ children }) {
  return (
    <th className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold">
      {children}
    </th>
  );
}

function Td({ children, className = "" }) {
  return <td className={`px-4 py-3 ${className}`}>{children}</td>;
}
