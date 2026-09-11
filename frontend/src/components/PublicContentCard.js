import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";
import { FileText, Plus, Trash2, Eye, EyeOff, MapPin, Inbox, Check, X } from "lucide-react";

const SERVICES = [
  { key: "car", label: "Car guarantee" },
  { key: "motorcycle", label: "Motorcycle guarantee" },
  { key: "computer", label: "Computer guarantee" },
  { key: "phone", label: "Phone guarantee" },
  { key: "heavy", label: "Heavy equipment guarantee" },
];
const FIELDS = [
  { k: "title_tet", label: "Title (Tetum)" },
  { k: "title_en", label: "Title (English)" },
  { k: "desc_tet", label: "Description (Tetum)" },
  { k: "desc_en", label: "Description (English)" },
];

const newId = () => `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

// Visitor reviews waiting for approval (submitted via /review or the Contact page).
function PendingReviews({ onApproved }) {
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(null);
  const load = () => api.get("/reviews?status=pending").then((r) => setRows(r.data)).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const act = async (id, action) => {
    setBusy(id);
    try {
      const { data } = await api.post(`/reviews/${id}/${action}`);
      toast.success(action === "approve" ? "Approved — now live on the homepage" : "Review rejected");
      if (action === "approve") onApproved(data.testimonials);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
    } finally {
      setBusy(null);
    }
  };
  if (!rows || rows.length === 0) return null;
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50/60 p-3 space-y-2" data-testid="pending-reviews">
      <div className="text-xs font-semibold text-amber-900 inline-flex items-center gap-1.5">
        <Inbox className="w-3.5 h-3.5" /> {rows.length} visitor review{rows.length > 1 ? "s" : ""} waiting for approval
      </div>
      {rows.map((r) => (
        <div key={r.id} className="rounded-md bg-white border border-amber-200 p-3 flex items-start gap-3" data-testid={`pending-review-${r.id}`}>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium">{r.name} <span className="text-[#B8860B]">{"★".repeat(r.rating || 0)}</span> <span className="text-stone-400 font-normal">· {r.role || "—"} · {r.lang.toUpperCase()}</span></div>
            <p className="text-sm text-stone-700 mt-1">“{r.text}”</p>
            {r.contact && <div className="text-[11px] text-stone-400 mt-1">Contact: {r.contact}</div>}
          </div>
          <div className="flex flex-col gap-1 shrink-0">
            <Button type="button" size="sm" className="h-7 bg-emerald-700 hover:bg-emerald-800" disabled={busy === r.id} onClick={() => act(r.id, "approve")} data-testid={`review-approve-${r.id}`}>
              <Check className="w-3.5 h-3.5 mr-1" /> Approve
            </Button>
            <Button type="button" size="sm" variant="outline" className="h-7 text-rose-700 border-rose-200" disabled={busy === r.id} onClick={() => act(r.id, "reject")} data-testid={`review-reject-${r.id}`}>
              <X className="w-3.5 h-3.5 mr-1" /> Reject
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

// Settings → Public Content: Services copy, homepage testimonials, Contact map.
export default function PublicContentCard({ s, onChange, defaults = {} }) {
  const svc = s.services_text || {};
  const setSvc = (key, field, val) => onChange("services_text", { ...svc, [key]: { ...(svc[key] || {}), [field]: val } });

  const list = Array.isArray(s.testimonials) && s.testimonials.length ? s.testimonials : null;
  const items = list || (defaults.testimonials || []).map((x) => ({ ...x }));
  const setItems = (next) => onChange("testimonials", next);
  const update = (id, patch) => setItems(items.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  const add = () => setItems([...items, { id: newId(), name: "", role: "", role_tet: "", text_en: "", text_tet: "", visible: true }]);
  const remove = (id) => setItems(items.filter((x) => x.id !== id));

  const faqList = Array.isArray(s.faq_items) && s.faq_items.length ? s.faq_items : null;
  const faqItems = faqList || (defaults.faq || []).map((x) => ({ ...x }));
  const setFaq = (next) => onChange("faq_items", next);
  const updFaq = (id, patch) => setFaq(faqItems.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  const addFaq = () => setFaq([...faqItems, { id: newId(), q_en: "", q_tet: "", a_en: "", a_tet: "", visible: true }]);

  return (
    <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-6" data-testid="public-content-card">
      <div className="flex items-center gap-2">
        <FileText className="w-5 h-5 text-[#1B2D5C]" />
        <h2 className="font-display text-xl">Public Content</h2>
      </div>

      <section className="space-y-3">
        <div className="text-xs uppercase tracking-wider text-stone-500 font-semibold">Services page text</div>
        <p className="text-xs text-stone-500 -mt-2">Leave a box empty to keep the built-in wording.</p>
        <div className="space-y-2">
          {SERVICES.map((sv) => (
            <details key={sv.key} className="rounded-lg border border-stone-200 bg-stone-50/60" data-testid={`svc-text-${sv.key}`}>
              <summary className="cursor-pointer px-3 py-2 text-sm font-medium select-none">{sv.label}</summary>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 pt-1">
                {FIELDS.map((f) => (
                  <div key={f.k} className="space-y-1">
                    <Label className="text-[11px] uppercase tracking-wider text-stone-500">{f.label}</Label>
                    {f.k.startsWith("desc") ? (
                      <Textarea rows={2} value={svc[sv.key]?.[f.k] || ""} placeholder={defaults.services?.[sv.key]?.[f.k] || ""}
                        onChange={(e) => setSvc(sv.key, f.k, e.target.value)} data-testid={`svc-${sv.key}-${f.k}`} />
                    ) : (
                      <Input value={svc[sv.key]?.[f.k] || ""} placeholder={defaults.services?.[sv.key]?.[f.k] || ""}
                        onChange={(e) => setSvc(sv.key, f.k, e.target.value)} data-testid={`svc-${sv.key}-${f.k}`} />
                    )}
                  </div>
                ))}
              </div>
            </details>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs uppercase tracking-wider text-stone-500 font-semibold">Homepage testimonials</div>
          <Button type="button" size="sm" variant="outline" onClick={add} data-testid="testimonial-add">
            <Plus className="w-3.5 h-3.5 mr-1" /> Add
          </Button>
        </div>
        <PendingReviews onApproved={(list) => list && onChange("testimonials", list)} />
        <div className="space-y-2">
          {items.map((tm, i) => (
            <div key={tm.id} className={`rounded-lg border p-3 space-y-2 ${tm.visible === false ? "border-stone-200 bg-stone-50 opacity-70" : "border-stone-200 bg-white"}`} data-testid={`testimonial-row-${i}`}>
              <div className="flex items-center gap-2">
                <Input className="flex-1" placeholder="Name" value={tm.name || ""} onChange={(e) => update(tm.id, { name: e.target.value })} data-testid={`testimonial-name-${i}`} />
                <Input className="flex-1" placeholder="Role (EN)" value={tm.role || ""} onChange={(e) => update(tm.id, { role: e.target.value })} data-testid={`testimonial-role-${i}`} />
                <Input className="flex-1" placeholder="Role (Tetum)" value={tm.role_tet || ""} onChange={(e) => update(tm.id, { role_tet: e.target.value })} />
                <Button type="button" variant="ghost" size="sm" className="h-8 px-2" title={tm.visible === false ? "Show on homepage" : "Hide from homepage"}
                  onClick={() => update(tm.id, { visible: tm.visible === false })} data-testid={`testimonial-toggle-${i}`}>
                  {tm.visible === false ? <EyeOff className="w-4 h-4 text-stone-400" /> : <Eye className="w-4 h-4 text-emerald-700" />}
                </Button>
                <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-rose-700" onClick={() => remove(tm.id)} data-testid={`testimonial-delete-${i}`}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <Textarea rows={2} placeholder="Quote (Tetum)" value={tm.text_tet || ""} onChange={(e) => update(tm.id, { text_tet: e.target.value })} data-testid={`testimonial-text-tet-${i}`} />
                <Textarea rows={2} placeholder="Quote (English)" value={tm.text_en || ""} onChange={(e) => update(tm.id, { text_en: e.target.value })} data-testid={`testimonial-text-en-${i}`} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs uppercase tracking-wider text-stone-500 font-semibold">FAQ (public page)</div>
          <Button type="button" size="sm" variant="outline" onClick={addFaq} data-testid="faq-add">
            <Plus className="w-3.5 h-3.5 mr-1" /> Add question
          </Button>
        </div>
        <div className="space-y-2">
          {faqItems.map((f, i) => (
            <div key={f.id} className={`rounded-lg border p-3 space-y-2 ${f.visible === false ? "border-stone-200 bg-stone-50 opacity-70" : "border-stone-200 bg-white"}`} data-testid={`faq-row-${i}`}>
              <div className="flex items-start gap-2">
                <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-2">
                  <Input placeholder="Question (Tetum)" value={f.q_tet || ""} onChange={(e) => updFaq(f.id, { q_tet: e.target.value })} data-testid={`faq-q-tet-${i}`} />
                  <Input placeholder="Question (English)" value={f.q_en || ""} onChange={(e) => updFaq(f.id, { q_en: e.target.value })} data-testid={`faq-q-en-${i}`} />
                  <Textarea rows={2} placeholder="Answer (Tetum)" value={f.a_tet || ""} onChange={(e) => updFaq(f.id, { a_tet: e.target.value })} data-testid={`faq-a-tet-${i}`} />
                  <Textarea rows={2} placeholder="Answer (English)" value={f.a_en || ""} onChange={(e) => updFaq(f.id, { a_en: e.target.value })} data-testid={`faq-a-en-${i}`} />
                </div>
                <div className="flex flex-col gap-1">
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2" title={f.visible === false ? "Show" : "Hide"}
                    onClick={() => updFaq(f.id, { visible: f.visible === false })} data-testid={`faq-toggle-${i}`}>
                    {f.visible === false ? <EyeOff className="w-4 h-4 text-stone-400" /> : <Eye className="w-4 h-4 text-emerald-700" />}
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-rose-700" onClick={() => setFaq(faqItems.filter((x) => x.id !== f.id))} data-testid={`faq-delete-${i}`}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-1.5">
        <Label className="text-xs uppercase tracking-wider text-stone-500 inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> Google Maps embed URL (optional)</Label>
        <Input value={s.map_embed_url || ""} onChange={(e) => onChange("map_embed_url", e.target.value)}
          placeholder="Leave empty to pin the address above automatically" data-testid="site-map-url" />
        <p className="text-[11px] text-stone-500">Google Maps → Share → Embed a map → copy the <code>src</code> URL for an exact pin.</p>
      </section>
    </Card>
  );
}
