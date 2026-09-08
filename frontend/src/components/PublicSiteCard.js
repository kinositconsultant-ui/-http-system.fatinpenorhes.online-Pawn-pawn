import { useState } from "react";
import { api, fileUrl } from "../lib/api";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Button } from "./ui/button";
import { Globe, Upload, RotateCcw, ExternalLink } from "lucide-react";
import { toast } from "sonner";

const SLOTS = [
  { key: "home_hero", label: "Homepage hero", group: "Homepage", wide: true },
  { key: "home_car", label: "Cars", group: "Homepage" },
  { key: "home_moto", label: "Motorcycles", group: "Homepage" },
  { key: "home_elek", label: "Electronics", group: "Homepage" },
  { key: "home_pez", label: "Heavy equipment", group: "Homepage" },
  { key: "svc_car", label: "Car guarantee", group: "Services" },
  { key: "svc_moto", label: "Motorcycle guarantee", group: "Services" },
  { key: "svc_computer", label: "Computer guarantee", group: "Services" },
  { key: "svc_phone", label: "Phone guarantee", group: "Services" },
  { key: "svc_heavy", label: "Heavy equipment guarantee", group: "Services" },
];

const CONTACT_FIELDS = [
  { k: "contact_phone", label: "Phone", placeholder: "+670 78372678" },
  { k: "contact_whatsapp", label: "WhatsApp number", placeholder: "+670 78372678" },
  { k: "contact_email", label: "Email", placeholder: "fatinpenhores@gmail.com" },
  { k: "contact_address", label: "Address", placeholder: "Caicoli, Dili, Timor-Leste" },
  { k: "contact_hours", label: "Opening hours", placeholder: "Segunda–Sábadu · 09:00–18:00" },
];

// Settings → Public Website: contact details + every image used on the public Home / Services pages.
export default function PublicSiteCard({ s, onChange, defaults = {} }) {
  const [busy, setBusy] = useState(null);
  const images = s.site_images || {};
  const setSlot = (key, val) => onChange("site_images", { ...images, [key]: val });

  const upload = async (key, file) => {
    setBusy(key);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setSlot(key, data.storage_path);
      toast.success("Image attached — click Save to publish");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(null);
    }
  };

  const preview = (key) => {
    const v = images[key];
    if (!v) return defaults[key] || "";
    return v.startsWith("http") ? v : fileUrl(v);
  };

  return (
    <Card className="p-6 border border-stone-200 shadow-none rounded-lg bg-white space-y-5" data-testid="public-site-card">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-[#1B2D5C]" />
          <h2 className="font-display text-xl">Public Website</h2>
        </div>
        <a href="/" target="_blank" rel="noopener noreferrer" className="text-xs text-[#1B2D5C] hover:underline inline-flex items-center gap-1" data-testid="public-site-open">
          Open homepage <ExternalLink className="w-3 h-3" />
        </a>
      </div>
      <p className="text-sm text-stone-600 -mt-2">
        Contact details appear in the footer, Contact page and WhatsApp buttons. Pictures replace the defaults on the Home and Services pages. Changes go live after <b>Save</b>.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {CONTACT_FIELDS.map((f) => (
          <div key={f.k} className="space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-stone-500">{f.label}</Label>
            <Input value={s[f.k] || ""} placeholder={f.placeholder} onChange={(e) => onChange(f.k, e.target.value)} data-testid={`site-${f.k}`} />
          </div>
        ))}
      </div>

      {["Homepage", "Services"].map((group) => (
        <div key={group}>
          <div className="text-xs uppercase tracking-wider text-stone-500 font-semibold mb-2">{group} pictures</div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {SLOTS.filter((x) => x.group === group).map((slot) => (
              <div key={slot.key} className={`rounded-lg border border-stone-200 overflow-hidden bg-stone-50 ${slot.wide ? "col-span-2" : ""}`} data-testid={`site-image-${slot.key}`}>
                <div className="aspect-[4/3] bg-stone-200 relative">
                  {preview(slot.key) && <img src={preview(slot.key)} alt="" className="absolute inset-0 w-full h-full object-cover" />}
                  {images[slot.key] && (
                    <span className="absolute top-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded bg-emerald-600 text-white">custom</span>
                  )}
                </div>
                <div className="p-2 space-y-1.5">
                  <div className="text-xs font-medium truncate">{slot.label}</div>
                  <div className="flex gap-1">
                    <label className="flex-1">
                      <input type="file" accept="image/*" className="hidden" data-testid={`site-image-upload-${slot.key}`}
                        onChange={(e) => e.target.files?.[0] && upload(slot.key, e.target.files[0])} />
                      <span className="inline-flex w-full items-center justify-center gap-1 text-[11px] px-2 py-1 rounded border border-stone-300 bg-white hover:border-[#1B2D5C] cursor-pointer">
                        <Upload className="w-3 h-3" /> {busy === slot.key ? "Uploading…" : "Replace"}
                      </span>
                    </label>
                    {images[slot.key] && (
                      <Button type="button" variant="ghost" size="sm" className="h-6 px-1.5" title="Reset to default"
                        onClick={() => setSlot(slot.key, "")} data-testid={`site-image-reset-${slot.key}`}>
                        <RotateCcw className="w-3 h-3" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </Card>
  );
}
