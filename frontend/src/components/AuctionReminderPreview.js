import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { CalendarClock, Send } from "lucide-react";
import { toast } from "sonner";

// Settings → exact auction-day reminder text + recipient count, with a "send test to my phone" action.
export default function AuctionReminderPreview() {
  const [p, setP] = useState(null);
  const [phone, setPhone] = useState("");
  const [sending, setSending] = useState(false);

  const load = () => api.get("/subscribers/auction-day-reminder/preview").then((r) => { setP(r.data); setPhone((cur) => cur || r.data.test_phone || ""); }).catch(() => {});
  useEffect(() => { load(); }, []);

  const sendTest = async () => {
    setSending(true);
    try {
      const r = await api.post("/subscribers/auction-day-reminder/test", { phone });
      toast.success(r.data.status === "mocked" ? `Test logged as MOCKED (WhatsApp not configured) → +${r.data.to}` : `Test sent to +${r.data.to}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to send test");
    } finally {
      setSending(false);
    }
  };

  if (!p) return null;
  return (
    <div className="rounded-lg border border-[#1B2D5C]/15 bg-[#1B2D5C]/[0.03] p-4 space-y-3" data-testid="auction-reminder-preview">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold inline-flex items-center gap-1">
          <CalendarClock className="w-3.5 h-3.5" /> Auction-day reminder (sent the day before)
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <span className="px-2 py-0.5 rounded-full bg-white border border-stone-200" data-testid="reminder-auction-date">Auction · {p.next_auction_date || "not set"}</span>
          <span className="px-2 py-0.5 rounded-full bg-white border border-stone-200" data-testid="reminder-send-on">Goes out · {p.send_on ? `${p.send_on} ${p.send_time_local}` : "—"}</span>
          <span className="px-2 py-0.5 rounded-full bg-[#1B2D5C] text-white" data-testid="reminder-recipients">{p.recipients} recipient{p.recipients === 1 ? "" : "s"}</span>
          <span className={`px-2 py-0.5 rounded-full border ${p.already_sent ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-white border-stone-200 text-stone-600"}`} data-testid="reminder-status">
            {p.already_sent ? `Sent for ${p.sent_for}` : p.last_sent_at ? `Last sent ${p.last_sent_at.slice(0, 16).replace("T", " ")}` : "Not sent yet"}
          </span>
        </div>
      </div>
      {p.body ? (
        <pre className="whitespace-pre-wrap font-sans text-xs bg-white border border-stone-200 rounded-md p-3 text-stone-700" data-testid="reminder-body">{p.body}</pre>
      ) : (
        <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md p-3" data-testid="reminder-no-date">
          Set the next auction date in Public Content to see the exact message.
        </div>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+670 7xxx xxxx" className="h-8 w-48 text-xs font-mono" data-testid="reminder-test-phone" />
        <Button type="button" size="sm" disabled={sending || !p.body} onClick={sendTest} className="h-8 bg-[#25D366] hover:bg-[#1EA952] text-white" data-testid="reminder-send-test">
          <Send className="w-3.5 h-3.5 mr-1" /> {sending ? "Sending…" : "Send test to my phone"}
        </Button>
        {!p.whatsapp_configured && <span className="text-[11px] text-stone-500">WhatsApp not configured — sends are logged as MOCKED.</span>}
      </div>
    </div>
  );
}
