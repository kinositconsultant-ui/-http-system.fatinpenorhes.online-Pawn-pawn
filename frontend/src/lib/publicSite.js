import { useEffect, useState } from "react";
import { api } from "./api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const PREVIEW_KEY = "fp_site_preview";

export const DEFAULT_CONTACT = {
  contact_phone: "+670 78372678",
  contact_whatsapp: "+670 78372678",
  contact_email: "fatinpenhores@gmail.com",
  contact_address: "Caicoli, Dili, Timor-Leste",
  contact_hours: "Segunda–Sábadu · 09:00–18:00",
  whatsapp_link: "https://wa.me/67078372678",
};

const EMPTY = { images: {}, contact: DEFAULT_CONTACT, rates: {}, services: {}, testimonials: [], faq: [], map_embed_url: "", next_auction_date: "", preview: false };

let cache = null;
let inflight = null;

const resolve = (data, preview = false) => ({
  images: Object.fromEntries(
    Object.entries(data.images || {}).map(([k, v]) => [k, v.startsWith("/api/") ? `${BACKEND_URL}${v}` : v])
  ),
  contact: { ...DEFAULT_CONTACT, ...(data.contact || {}) },
  rates: data.rates || {},
  services: data.services || {},
  testimonials: data.testimonials || [],
  faq: data.faq || [],
  map_embed_url: data.map_embed_url || "",
  next_auction_date: data.next_auction_date || "",
  preview,
});

// Settings → "Preview changes" stores the resolved draft here and opens /?preview=1.
export const isPreviewMode = () => new URLSearchParams(window.location.search).get("preview") === "1";
export function readPreviewDraft() {
  if (!isPreviewMode()) return null;
  try {
    const raw = sessionStorage.getItem(PREVIEW_KEY) || localStorage.getItem(PREVIEW_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function loadPublicSite(force = false) {
  const draft = readPreviewDraft();
  if (draft) return Promise.resolve(resolve(draft, true));
  if (cache && !force) return Promise.resolve(cache);
  if (!inflight || force) {
    inflight = api
      .get("/public/site")
      .then((r) => { cache = resolve(r.data); return cache; })
      .catch(() => { cache = EMPTY; return cache; })
      .finally(() => { inflight = null; });
  }
  return inflight;
}

// Images, contact, rates, copy for the public website — editable by admins in Settings.
export function usePublicSite() {
  const [site, setSite] = useState(cache || EMPTY);
  useEffect(() => {
    let alive = true;
    loadPublicSite().then((s) => alive && setSite(s));
    return () => { alive = false; };
  }, []);
  return site;
}
