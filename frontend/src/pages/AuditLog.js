import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useLang } from "../context/LangContext";

export default function AuditLog() {
  const { t } = useLang();
  const [rows, setRows] = useState([]);
  const [resource, setResource] = useState("");

  useEffect(() => {
    const q = resource ? `?resource=${resource}` : "";
    api.get(`/audit-log${q}`).then((r) => setRows(r.data));
  }, [resource]);

  return (
    <div className="space-y-6" data-testid="audit-log-root">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-eyebrow">{t("audit_log")}</div>
          <h1 className="font-display text-2xl sm:text-3xl md:text-4xl font-semibold mt-1">{t("audit_log")}</h1>
        </div>
        <select
          value={resource}
          onChange={(e) => setResource(e.target.value)}
          className="px-3 py-2 rounded-md border border-stone-200 text-sm bg-white"
          data-testid="audit-resource-filter"
        >
          <option value="">All resources</option>
          <option value="contract">contract</option>
          <option value="payment">payment</option>
          <option value="settings">settings</option>
        </select>
      </header>

      <div className="rounded-lg border border-stone-200 bg-white overflow-x-auto">
        <table className="min-w-full text-sm" data-testid="audit-log-table">
          <thead className="bg-stone-50 text-left">
            <tr>
              <Th>When</Th>
              <Th>Actor</Th>
              <Th>Role</Th>
              <Th>Action</Th>
              <Th>Resource</Th>
              <Th>ID</Th>
              <Th>Details</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100 align-top">
                <Td className="whitespace-nowrap">
                  {new Date(r.created_at).toLocaleString()}
                </Td>
                <Td>{r.actor_email}</Td>
                <Td>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 border border-stone-200">
                    {r.actor_role}
                  </span>
                </Td>
                <Td className="font-medium">{r.action}</Td>
                <Td>{r.resource}</Td>
                <Td className="text-xs text-stone-500">{r.resource_id?.slice(0, 8)}</Td>
                <Td className="text-xs text-stone-600 max-w-md break-words">
                  {Object.keys(r.payload || {}).length > 0
                    ? JSON.stringify(r.payload)
                    : "—"}
                </Td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="p-8 text-center text-stone-500" colSpan="7">
                  No log entries
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
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
