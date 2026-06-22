import { useState } from "react";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import { MapPin, Mail, Phone } from "lucide-react";
import { toast } from "sonner";

const blank = { name: "", email: "", phone: "", message: "" };

export default function Contact() {
  const { t } = useLang();
  const [form, setForm] = useState(blank);
  const [sending, setSending] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      await api.post("/public/contact", form);
      toast.success(t("message_sent"));
      setForm(blank);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
    setSending(false);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 lg:px-10 py-20 grid md:grid-cols-2 gap-12">
      <div>
        <div className="text-eyebrow">{t("contact")}</div>
        <h1 className="font-display text-4xl sm:text-5xl mt-1">{t("contact_us")}</h1>
        <p className="text-stone-600 mt-4 max-w-md">
          Send us a message about a pawn, payment, or an auction listing. We typically reply within one business day.
        </p>
        <div className="mt-8 space-y-4 text-sm">
          <div className="flex items-center gap-3 text-stone-700">
            <MapPin className="w-4 h-4 text-[#1B2D5C]" /> Caicoli, Dili, Timor-Leste
          </div>
          <div className="flex items-center gap-3 text-stone-700">
            <Mail className="w-4 h-4 text-[#1B2D5C]" /> fatinpenhores@gmail.com
          </div>
          <div className="flex items-center gap-3 text-stone-700">
            <Phone className="w-4 h-4 text-[#1B2D5C]" /> +670 78372678
          </div>
        </div>
      </div>
      <form
        onSubmit={submit}
        className="bg-white border border-stone-200 rounded-lg p-6 space-y-4"
        data-testid="contact-form"
      >
        <div className="space-y-1.5">
          <Label>{t("full_name")}</Label>
          <Input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
            data-testid="contact-name"
          />
        </div>
        <div className="space-y-1.5">
          <Label>{t("email")}</Label>
          <Input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
            data-testid="contact-email"
          />
        </div>
        <div className="space-y-1.5">
          <Label>{t("phone")}</Label>
          <Input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            data-testid="contact-phone"
          />
        </div>
        <div className="space-y-1.5">
          <Label>Message</Label>
          <Textarea
            rows={5}
            value={form.message}
            onChange={(e) => setForm({ ...form, message: e.target.value })}
            required
            data-testid="contact-message"
          />
        </div>
        <Button
          type="submit"
          disabled={sending}
          className="w-full bg-[#1B2D5C] hover:bg-[#0F1B3A]"
          data-testid="contact-submit"
        >
          {sending ? "…" : t("send_message")}
        </Button>
      </form>
    </div>
  );
}
