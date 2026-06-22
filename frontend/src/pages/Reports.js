import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";

const REPORTS = [
  { key: "loans", labelKey: "loan_report" },
  { key: "payments", labelKey: "payment_report" },
  { key: "profit", labelKey: "profit_report" },
  { key: "overdue", labelKey: "overdue_report" },
  { key: "clients", labelKey: "client_report" },
  { key: "contracts", labelKey: "contract_report" },
];

export default function Reports() {
  const { t } = useLang();
  const [type, setType] = useState("loans");
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get(`/reports/${type}`).then((r) => setRows(r.data));
  }, [type]);

  const columns = rows[0] ? Object.keys(rows[0]) : [];

  const exportCsv = () => {
    if (rows.length === 0) return;
    const cols = Object.keys(rows[0]);
    const csv =
      cols.join(",") +
      "\n" +
      rows
        .map((r) =>
          cols
            .map((c) => {
              const v = r[c] == null ? "" : String(r[c]).replace(/"/g, '""');
              return /[,"\n]/.test(v) ? `"${v}"` : v;
            })
            .join(",")
        )
        .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${type}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6" data-testid="reports-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("reports")}</div>
          <h1 className="font-display text-4xl font-semibold mt-1">{t("reports")}</h1>
        </div>
        <div className="flex gap-3">
          <Select value={type} onValueChange={setType}>
            <SelectTrigger className="w-64" data-testid="report-type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {REPORTS.map((r) => (
                <SelectItem key={r.key} value={r.key}>
                  {t(r.labelKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            onClick={exportCsv}
            data-testid="report-export-csv"
            className="px-4 py-2 rounded-md text-sm bg-[#2F4F4F] hover:bg-[#1D3333] text-white transition"
          >
            Export CSV
          </button>
        </div>
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="report-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  className="px-4 py-3 text-xs uppercase tracking-wider text-stone-500 font-semibold"
                >
                  {c.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.id || i} className="border-t border-stone-100">
                {columns.map((c) => (
                  <td key={c} className="px-4 py-3">
                    {typeof row[c] === "object" && row[c] !== null
                      ? JSON.stringify(row[c])
                      : String(row[c] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="p-8 text-center text-stone-500" colSpan="20">
                  No data
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
