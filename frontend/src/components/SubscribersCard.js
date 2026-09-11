import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Bell, Trash2 } from "lucide-react";
import { toast } from "sonner";

const KIND = { car: "Cars", motorcycle: "Motorcycles", electronic: "Electronics", pezadu: "Heavy eq." };

// Settings → WhatsApp alert subscribers (visitors who opted in on the public homepage).
export default function SubscribersCard() {
  const [rows, setRows] = useState([]);
  const load = () => api.get("/subscribers").then((r) => setRows(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const remove = async (id) => {
    if (!window.confirm("Remove this subscriber?")) return;
    try {
      await api.delete(`/subscribers/${id}`);
      toast.success("Subscriber removed");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const counts = {
    date: rows.filter((r) => r.auction_reminder).length,
    ...Object.fromEntries(Object.keys(KIND).map((k) => [k, rows.filter((r) => (r.kinds || []).includes(k)).length])),
  };

  return (
    <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-4" data-testid="subscribers-card">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-[#1B2D5C]" />
          <h2 className="font-display text-xl">WhatsApp Alert Subscribers</h2>
          <span className="text-xs px-2 py-0.5 rounded-full bg-stone-100 text-stone-600" data-testid="subscribers-count">{rows.length}</span>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <span className="px-2 py-0.5 rounded-full bg-[#1B2D5C]/5 border border-[#1B2D5C]/15">Auction date · {counts.date}</span>
          {Object.entries(KIND).map(([k, l]) => (
            <span key={k} className="px-2 py-0.5 rounded-full bg-stone-50 border border-stone-200">{l} · {counts[k]}</span>
          ))}
        </div>
      </div>
      <p className="text-xs text-stone-500 -mt-2">
        Visitors sign up on the homepage auction card. They're messaged automatically when the auction date changes or a matching item is listed (WhatsApp must be configured; otherwise sends are logged as MOCKED).
      </p>
      {rows.length === 0 ? (
        <div className="text-sm text-stone-400 py-4 text-center" data-testid="subscribers-empty">No subscribers yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-stone-50 text-left text-[10px] uppercase tracking-wider text-stone-500">
              <tr><th className="px-3 py-2">Phone</th><th className="px-3 py-2">Alerts</th><th className="px-3 py-2">Lang</th><th className="px-3 py-2">Since</th><th className="px-3 py-2" /></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-stone-100" data-testid={`subscriber-row-${r.id}`}>
                  <td className="px-3 py-2 font-mono text-xs">+{r.phone}</td>
                  <td className="px-3 py-2 text-xs">{[r.auction_reminder ? "Auction date" : null, ...(r.kinds || []).map((k) => KIND[k] || k)].filter(Boolean).join(", ")}</td>
                  <td className="px-3 py-2 text-xs uppercase">{r.lang}</td>
                  <td className="px-3 py-2 text-xs text-stone-500">{(r.created_at || "").slice(0, 10)}</td>
                  <td className="px-3 py-2 text-right">
                    <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-rose-700" onClick={() => remove(r.id)} data-testid={`subscriber-delete-${r.id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
