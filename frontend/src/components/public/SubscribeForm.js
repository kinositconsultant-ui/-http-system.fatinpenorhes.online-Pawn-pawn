import { useState } from "react";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Bell, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

const COPY = {
  en: { title: "Get WhatsApp alerts", sub: "We'll message you when the auction date is announced or a new item is listed.",
        date: "Auction date", car: "New cars", motorcycle: "New motorcycles", electronic: "Electronics", pezadu: "Heavy equipment",
        phone: "WhatsApp number", send: "Notify me", ok: "You're on the list — we'll WhatsApp you." },
  tet: { title: "Simu avizu WhatsApp", sub: "Ami sei haruka mensajen bainhira data leilaun sai ka sasán foun tama lista.",
         date: "Data leilaun", car: "Karreta foun", motorcycle: "Motor foun", electronic: "Eletróniku", pezadu: "Pezadu",
         phone: "Númeru WhatsApp", send: "Avizu ha'u", ok: "Ita-boot iha lista ona — ami sei WhatsApp ita-boot." },
};
const KINDS = ["car", "motorcycle", "electronic", "pezadu"];

// Visitor opt-in for auction-date and new-listing WhatsApp alerts (homepage auction card).
export default function SubscribeForm() {
  const { lang } = useLang();
  const c = COPY[lang] || COPY.en;
  const [phone, setPhone] = useState("");
  const [date, setDate] = useState(true);
  const [kinds, setKinds] = useState(["car", "motorcycle"]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const toggle = (k) => setKinds((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/public/subscribe", { phone, lang, auction_reminder: date, kinds });
      setDone(true);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not subscribe");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="mt-6 rounded-xl bg-emerald-500/15 border border-emerald-400/30 p-3 text-sm text-emerald-100 flex items-start gap-2" data-testid="subscribe-done">
        <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" /> {c.ok}
      </div>
    );
  }
  const chip = (on) => `px-2.5 py-1 rounded-full text-[11px] border transition-colors ${on ? "bg-[#F0B435] text-[#0F1B3A] border-[#F0B435]" : "border-white/25 text-white/80 hover:border-white/60"}`;
  return (
    <form onSubmit={submit} className="mt-6 rounded-xl bg-white/[0.07] border border-white/10 p-4 space-y-3" data-testid="subscribe-form">
      <div className="flex items-center gap-2 text-sm font-semibold"><Bell className="w-4 h-4 text-[#F0B435]" /> {c.title}</div>
      <p className="text-xs text-white/65">{c.sub}</p>
      <div className="flex flex-wrap gap-1.5">
        <button type="button" onClick={() => setDate((v) => !v)} className={chip(date)} data-testid="subscribe-kind-date">{c.date}</button>
        {KINDS.map((k) => (
          <button key={k} type="button" onClick={() => toggle(k)} className={chip(kinds.includes(k))} data-testid={`subscribe-kind-${k}`}>{c[k]}</button>
        ))}
      </div>
      <div className="flex gap-2">
        <Input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={`${c.phone} · +670 7…`} inputMode="tel"
          className="bg-white/10 border-white/20 text-white placeholder:text-white/40" data-testid="subscribe-phone" />
        <Button type="submit" disabled={busy} className="bg-[#F0B435] hover:bg-[#d9a12e] text-[#0F1B3A] rounded-full shrink-0" data-testid="subscribe-submit">
          {busy ? "…" : c.send}
        </Button>
      </div>
    </form>
  );
}
