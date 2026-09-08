import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useLang } from "../../context/LangContext";
import { Button } from "../ui/button";
import { Gavel, ArrowRight, Lock, Car, Bike, Truck, Laptop } from "lucide-react";

const KIND_ICON = { car: Car, motorcycle: Bike, pezadu: Truck, electronic: Laptop };
const KIND_LABEL = {
  en: { car: "Car", motorcycle: "Motorcycle", pezadu: "Heavy equipment", electronic: "Electronics" },
  tet: { car: "Karreta", motorcycle: "Motor", pezadu: "Pezadu", electronic: "Eletróniku" },
};
const fmtUsd = (n) => `USD $${Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

const COPY = {
  en: { eyebrow: "Next auction", title: "Coming up for auction", locked: "Listing is password-protected — ask us for the visitor pass.",
        items: "items listed", cta: "See full auction", countdown: "Auction day in", today: "Auction day is today!", past: "Auction date has passed", nodate: "Date to be announced",
        d: "days", h: "hrs", m: "min", s: "sec", start: "Starting price" },
  tet: { eyebrow: "Leilaun tuir mai", title: "Sasán ne'ebé sei tama leilaun", locked: "Lista protejidu ho senha — husu ami pase bizitante.",
         items: "sasán iha lista", cta: "Haree leilaun tomak", countdown: "Loron leilaun iha", today: "Leilaun mak ohin!", past: "Data leilaun liu ona", nodate: "Data sei anunsia",
         d: "loron", h: "oras", m: "min", s: "seg", start: "Folin hahú" },
};

function useCountdown(dateStr) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!dateStr) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [dateStr]);
  if (!dateStr) return null;
  const target = new Date(`${dateStr}T09:00:00`).getTime(); // auctions start 09:00 local
  if (Number.isNaN(target)) return null;
  const diff = target - now;
  const abs = Math.max(0, diff);
  return {
    diff,
    d: Math.floor(abs / 86400000),
    h: Math.floor((abs % 86400000) / 3600000),
    m: Math.floor((abs % 3600000) / 60000),
    s: Math.floor((abs % 60000) / 1000),
  };
}

// Homepage teaser: next 3 listed auction items + live countdown to next_auction_date (Settings).
export default function AuctionHighlights({ nextDate }) {
  const { lang } = useLang();
  const c = COPY[lang] || COPY.en;
  const [data, setData] = useState(null);
  const cd = useCountdown(data?.next_auction_date || nextDate);

  useEffect(() => {
    api.get("/public/auction-highlights?limit=3").then((r) => setData(r.data)).catch(() => setData({ items: [], total: 0, locked: false }));
  }, []);

  if (!data || (data.total === 0 && !(data.next_auction_date || nextDate))) return null;
  const sameDay = cd && cd.diff <= 0 && cd.diff > -86400000;

  return (
    <section className="max-w-7xl mx-auto px-6 lg:px-10 mt-20 md:mt-28" data-testid="home-auction-highlights">
      <div className="rounded-3xl border border-stone-200 bg-white shadow-sm overflow-hidden">
        <div className="grid lg:grid-cols-[1fr_1.6fr]">
          <div className="relative bg-[#0F1B3A] text-white p-8 md:p-10 flex flex-col justify-between overflow-hidden">
            <div className="absolute -left-20 -bottom-20 w-72 h-72 rounded-full bg-[#B8860B]/25 blur-3xl pointer-events-none" />
            <div className="relative">
              <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-[#F0B435] font-semibold">
                <Gavel className="w-4 h-4" /> {c.eyebrow}
              </div>
              <h2 className="font-display text-3xl md:text-4xl mt-3 leading-tight">{c.title}</h2>
              <div className="mt-2 text-white/70 text-sm" data-testid="home-auction-total">{data.total} {c.items}</div>
            </div>
            <div className="relative mt-8">
              {cd ? (
                cd.diff > 0 ? (
                  <>
                    <div className="text-[10px] uppercase tracking-[0.3em] text-white/60">{c.countdown}</div>
                    <div className="mt-2 grid grid-cols-4 gap-2" data-testid="home-auction-countdown">
                      {[["d", cd.d], ["h", cd.h], ["m", cd.m], ["s", cd.s]].map(([k, v]) => (
                        <div key={k} className="rounded-xl bg-white/10 border border-white/10 py-3 text-center">
                          <div className="font-display text-2xl md:text-3xl tabular-nums leading-none">{String(v).padStart(2, "0")}</div>
                          <div className="text-[10px] uppercase tracking-widest text-white/60 mt-1">{c[k]}</div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="font-display text-2xl text-[#F0B435]" data-testid="home-auction-countdown">{sameDay ? c.today : c.past}</div>
                )
              ) : (
                <div className="text-white/70 text-sm" data-testid="home-auction-countdown">{c.nodate}</div>
              )}
              <Link to="/auction" className="inline-block mt-6">
                <Button className="bg-[#C17767] hover:bg-[#A96253] text-white rounded-full h-11 px-5" data-testid="home-auction-cta">
                  {c.cta} <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>
          </div>
          <div className="p-6 md:p-8">
            {data.locked ? (
              <div className="h-full min-h-[220px] flex flex-col" data-testid="home-auction-locked">
                <div className="grid grid-cols-3 gap-3 flex-1">
                  {(data.teasers || []).map((tz) => {
                    const Icon = KIND_ICON[tz.item_type] || Car;
                    return (
                      <div key={tz.id} className="relative rounded-2xl overflow-hidden border border-stone-200 bg-stone-100 aspect-[4/5] sm:aspect-[4/3]" data-testid={`home-auction-teaser-${tz.id}`}>
                        {tz.photo_url ? (
                          <img src={tz.photo_url} alt="" className="absolute inset-0 w-full h-full object-cover blur-md scale-110 select-none pointer-events-none" />
                        ) : (
                          <div className="absolute inset-0 bg-gradient-to-br from-[#1B2D5C]/15 to-[#C17767]/15" />
                        )}
                        <div className="absolute inset-0 bg-[#0F1B3A]/25" />
                        <div className="relative h-full flex flex-col items-center justify-center text-center p-3">
                          <div className="w-11 h-11 rounded-full bg-white/85 backdrop-blur flex items-center justify-center shadow">
                            <Icon className="w-5 h-5 text-[#1B2D5C]" />
                          </div>
                          <div className="mt-2 text-[10px] uppercase tracking-widest font-semibold text-white drop-shadow">{KIND_LABEL[lang]?.[tz.item_type] || tz.item_type}</div>
                          {tz.manufacture_year && <div className="text-xs text-white/90 drop-shadow">{tz.manufacture_year}</div>}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-3 text-xs text-stone-500 inline-flex items-center gap-1.5"><Lock className="w-3.5 h-3.5" /> {c.locked}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {data.items.map((it) => {
                  const Icon = KIND_ICON[it.item_type] || Car;
                  const title = it.name || `${it.brand} ${it.model}`.trim();
                  return (
                    <Link to="/auction" key={it.id} className="group rounded-2xl border border-stone-200 overflow-hidden hover:shadow-lg transition-shadow" data-testid={`home-auction-item-${it.id}`}>
                      <div className="aspect-[4/3] bg-stone-100 relative overflow-hidden">
                        {it.photo_url ? (
                          <img src={it.photo_url} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center"><Icon className="w-10 h-10 text-stone-300" /></div>
                        )}
                        {it.manufacture_year && <span className="absolute top-2 left-2 text-[10px] px-2 py-0.5 rounded-full bg-white/90 text-stone-700">{it.manufacture_year}</span>}
                      </div>
                      <div className="p-3">
                        <div className="font-display text-base leading-tight truncate">{title || "—"}</div>
                        <div className="text-[10px] uppercase tracking-widest text-stone-500 mt-1">{c.start}</div>
                        <div className="font-semibold text-[#1B2D5C]">{fmtUsd(it.starting_price)}</div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
