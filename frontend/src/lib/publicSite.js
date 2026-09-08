import { useEffect, useState } from "react";
import { api } from "./api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const DEFAULT_CONTACT = {
  contact_phone: "+670 78372678",
  contact_whatsapp: "+670 78372678",
  contact_email: "fatinpenhores@gmail.com",
  contact_address: "Caicoli, Dili, Timor-Leste",
  contact_hours: "Segunda–Sábadu · 09:00–18:00",
  whatsapp_link: "https://wa.me/67078372678",
};

let cache = null;
let inflight = null;

const resolve = (data) => ({
  images: Object.fromEntries(
    Object.entries(data.images || {}).map(([k, v]) => [k, v.startsWith("/api/") ? `${BACKEND_URL}${v}` : v])
  ),
  contact: { ...DEFAULT_CONTACT, ...(data.contact || {}) },
});

export function loadPublicSite(force = false) {
  if (cache && !force) return Promise.resolve(cache);
  if (!inflight || force) {
    inflight = api
      .get("/public/site")
      .then((r) => { cache = resolve(r.data); return cache; })
      .catch(() => { cache = { images: {}, contact: DEFAULT_CONTACT }; return cache; })
      .finally(() => { inflight = null; });
  }
  return inflight;
}

// Images + contact details for the public website, editable by admins in Settings → Public Website.
export function usePublicSite() {
  const [site, setSite] = useState(cache || { images: {}, contact: DEFAULT_CONTACT });
  useEffect(() => {
    let alive = true;
    loadPublicSite().then((s) => alive && setSite(s));
    return () => { alive = false; };
  }, []);
  return site;
}
