import { useState } from "react";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { Button } from "../ui/button";
import { Star, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

const COPY = {
  en: { title: "Leave a review", sub: "Tell others about your experience with Fatin Penhores. Reviews are checked by our team before they appear on the homepage.",
        name: "Your name", role: "Where you're from / what you do (optional)", text: "Your review", contact: "Phone or email (optional, never published)",
        send: "Send review", thanks: "Thank you! Your review has been received and will appear after approval." },
  tet: { title: "Husik ita-boot nia opiniaun", sub: "Konta ba ema seluk kona-ba ita-boot nia esperiénsia ho Fatin Penhores. Ami nia ekipa verifika opiniaun molok publika iha pájina prinsipál.",
         name: "Ita-boot nia naran", role: "Husi ne'ebé / servisu saida (opsionál)", text: "Ita-boot nia opiniaun", contact: "Telefone ka email (opsionál, la publika)",
         send: "Haruka opiniaun", thanks: "Obrigadu! Ami simu ona ita-boot nia opiniaun, sei mosu hafoin aprovasaun." },
};

// Public testimonial submission (Contact page + /review). Held for admin approval.
export default function ReviewForm({ compact = false }) {
  const { lang } = useLang();
  const c = COPY[lang] || COPY.en;
  const [f, setF] = useState({ name: "", role: "", text: "", contact: "", rating: 5 });
  const [hover, setHover] = useState(0);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      await api.post("/public/reviews", { ...f, lang });
      setDone(true);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not send review");
    } finally {
      setSending(false);
    }
  };

  if (done) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 flex items-start gap-3" data-testid="review-thanks">
        <CheckCircle2 className="w-5 h-5 text-emerald-700 mt-0.5 shrink-0" />
        <p className="text-sm text-emerald-900">{c.thanks}</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className={`rounded-xl border border-stone-200 bg-white ${compact ? "p-5" : "p-6 md:p-8"} space-y-3`} data-testid="review-form">
      <div className="flex items-center gap-2">
        <Star className="w-5 h-5 text-[#B8860B]" />
        <h2 className="font-display text-xl md:text-2xl text-[#1B2D5C]">{c.title}</h2>
      </div>
      <p className="text-sm text-stone-600">{c.sub}</p>
      <div className="flex items-center gap-1" data-testid="review-stars" onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" onClick={() => setF((p) => ({ ...p, rating: n }))} onMouseEnter={() => setHover(n)}
            className="p-0.5 transition-transform hover:scale-110" aria-label={`${n} star`} data-testid={`review-star-${n}`}>
            <Star className={`w-7 h-7 ${(hover || f.rating) >= n ? "fill-[#B8860B] text-[#B8860B]" : "text-stone-300"}`} />
          </button>
        ))}
        <span className="ml-2 text-sm text-stone-500" data-testid="review-rating-value">{f.rating}/5</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input required minLength={2} placeholder={c.name} value={f.name} onChange={set("name")} data-testid="review-name" />
        <Input placeholder={c.role} value={f.role} onChange={set("role")} data-testid="review-role" />
      </div>
      <Textarea required minLength={10} maxLength={600} rows={4} placeholder={c.text} value={f.text} onChange={set("text")} data-testid="review-text" />
      <Input placeholder={c.contact} value={f.contact} onChange={set("contact")} data-testid="review-contact" />
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] text-stone-400">{f.text.length}/600</span>
        <Button type="submit" disabled={sending} className="bg-[#1B2D5C] hover:bg-[#0F1B3A] rounded-full px-6" data-testid="review-submit">
          {sending ? "…" : c.send}
        </Button>
      </div>
    </form>
  );
}
