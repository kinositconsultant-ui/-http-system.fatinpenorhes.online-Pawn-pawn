import { Link } from "react-router-dom";
import { useLang } from "../../context/LangContext";
import { Button } from "../../components/ui/button";
import {
  ArrowRight, ShieldCheck, Clock, FileSignature, Car, Bike, Smartphone, Truck,
  UserPlus, Search, Banknote, KeyRound, Quote, MessageCircle, Calculator, MapPin, CheckCircle2, Star,
} from "lucide-react";
import { usePublicSite } from "../../lib/publicSite";
import AuctionHighlights from "../../components/public/AuctionHighlights";

const FALLBACK = {
  hero: "https://static.prod-images.emergentagent.com/jobs/7e09fb06-54ad-4312-b74c-802a3b1278f0/images/2814e99c56332a78c1decdb6595a9ed90842ef98c7d1b806d0df3958c7e06646.jpeg",
  car: "https://static.prod-images.emergentagent.com/jobs/7e09fb06-54ad-4312-b74c-802a3b1278f0/images/c34836af03801ceb2a1d17b24dab9755c02eddde6a528026f05954b4be4b4793.jpeg",
  moto: "https://static.prod-images.emergentagent.com/jobs/7e09fb06-54ad-4312-b74c-802a3b1278f0/images/565ecc42cfac57fb39339659fe1acd0a3af360ee75ed9ef093548424128fb1b7.jpeg",
  elek: "https://static.prod-images.emergentagent.com/jobs/7e09fb06-54ad-4312-b74c-802a3b1278f0/images/c6ae9d885b3a3f1fe0316ec4b308e772149fff6849b711dc78d0dcec9a7aa587.jpeg",
  pez: "https://static.prod-images.emergentagent.com/jobs/7e09fb06-54ad-4312-b74c-802a3b1278f0/images/4345338453db1b69af389469d91b99f0e3a12d6c751285cfa1f2abd0e70fde52.jpeg",
};
const SLOT = { hero: "home_hero", car: "home_car", moto: "home_moto", elek: "home_elek", pez: "home_pez" };

const CATEGORIES = [
  { key: "car", Icon: Car, titleKey: "cat_car_title", bodyKey: "cat_car_body", rateKey: "car", span: "lg:col-span-2 lg:row-span-2 aspect-[4/5] lg:aspect-auto" },
  { key: "moto", Icon: Bike, titleKey: "cat_moto_title", bodyKey: "cat_moto_body", rateKey: "motorcycle", span: "aspect-[4/5] lg:aspect-[4/3]" },
  { key: "elek", Icon: Smartphone, titleKey: "cat_elek_title", bodyKey: "cat_elek_body", rateKey: "electronic", span: "aspect-[4/5] lg:aspect-[4/3]" },
  { key: "pez", Icon: Truck, titleKey: "cat_pez_title", bodyKey: "cat_pez_body", rateKey: "pezadu", span: "lg:col-span-2 aspect-[4/5] sm:aspect-[16/9]" },
];

const STEPS = [
  { Icon: UserPlus, titleKey: "step1_title", bodyKey: "step1_body", tone: "bg-[#1B2D5C]" },
  { Icon: Search, titleKey: "step2_title", bodyKey: "step2_body", tone: "bg-[#4C7F62]" },
  { Icon: Banknote, titleKey: "step3_title", bodyKey: "step3_body", tone: "bg-[#B8860B]" },
  { Icon: KeyRound, titleKey: "step4_title", bodyKey: "step4_body", tone: "bg-[#C17767]" },
];

const VALUES = [
  { Icon: ShieldCheck, titleKey: "home_value_1_title", bodyKey: "home_value_1_body" },
  { Icon: Clock, titleKey: "home_value_2_title", bodyKey: "home_value_2_body" },
  { Icon: FileSignature, titleKey: "home_value_3_title", bodyKey: "home_value_3_body" },
];

const TESTIMONIALS = [
  { textKey: "testim_1", nameKey: "testim_1_name", roleKey: "testim_1_role" },
  { textKey: "testim_2", nameKey: "testim_2_name", roleKey: "testim_2_role" },
  { textKey: "testim_3", nameKey: "testim_3_name", roleKey: "testim_3_role" },
];

const Eyebrow = ({ children }) => (
  <div className="text-[11px] uppercase tracking-[0.28em] font-semibold text-[#C17767] mb-3">{children}</div>
);
const H2 = ({ children }) => (
  <h2 className="font-display text-3xl md:text-4xl lg:text-5xl tracking-tight text-stone-900 leading-tight">{children}</h2>
);

export default function Home() {
  const { t, lang } = useLang();
  const site = usePublicSite();
  const rateRange = (() => {
    const v = Object.values(site.rates || {}).map(Number).filter((n) => n > 0);
    if (!v.length) return "10–15%";
    const lo = Math.min(...v), hi = Math.max(...v);
    return lo === hi ? `${lo}%` : `${lo}–${hi}%`;
  })();
  const img = (k) => site.images[SLOT[k]] || FALLBACK[k];
  return (
    <div className="pb-20 fp-tais-soft" data-testid="home-root">
      <Hero t={t} img={img} contact={site.contact} rateRange={rateRange} />
      <section className="max-w-7xl mx-auto px-6 lg:px-10 -mt-12 md:-mt-16 relative z-10">
        <div className="grid md:grid-cols-3 gap-4 md:gap-6">
          {VALUES.map((v, i) => (
            <div key={i} className="fp-rise p-6 rounded-xl border border-stone-200 bg-white shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-[transform,box-shadow]"
              style={{ animationDelay: `${0.35 + i * 0.1}s` }} data-testid={`home-value-${i}`}>
              <div className="w-10 h-10 rounded-lg bg-[#1B2D5C]/5 border border-[#1B2D5C]/10 flex items-center justify-center">
                <v.Icon className="w-5 h-5 text-[#1B2D5C]" />
              </div>
              <h3 className="font-display text-lg md:text-xl mt-4">{t(v.titleKey)}</h3>
              <p className="text-stone-600 text-sm mt-2 leading-relaxed">{t(v.bodyKey)}</p>
            </div>
          ))}
        </div>
      </section>
      <Categories t={t} img={img} rates={site.rates} />
      <Steps t={t} />
      <AuctionHighlights nextDate={site.next_auction_date} />
      <Testimonials t={t} items={site.testimonials} lang={lang} />
      <FinalCta t={t} contact={site.contact} />
    </div>
  );
}

function Hero({ t, img, contact, rateRange }) {
  return (
    <section className="relative overflow-hidden" data-testid="home-hero">
      <div className="absolute inset-0">
        <img alt="" src={img("hero")} className="w-full h-full object-cover object-[70%_center]" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0F1B3A]/95 via-[#1B2D5C]/80 to-[#1B2D5C]/20" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0F1B3A]/70 via-transparent to-transparent" />
      </div>
      <div className="relative max-w-7xl mx-auto px-6 lg:px-10 pt-20 pb-28 md:pt-28 md:pb-36 lg:pt-32 lg:pb-40 text-white grid lg:grid-cols-[1.4fr_1fr] gap-10 items-end">
        <div>
          <div className="fp-rise inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-white/85 mb-6 px-3 py-1 rounded-full border border-white/15 bg-white/5 backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {t("tagline")}
          </div>
          <h1 className="fp-rise font-display text-4xl sm:text-5xl lg:text-6xl tracking-tight max-w-3xl leading-[1.05]" style={{ animationDelay: "0.08s" }}>
            {t("hero_title")}
          </h1>
          <p className="fp-rise mt-6 max-w-xl text-stone-100/90 text-base sm:text-lg leading-relaxed" style={{ animationDelay: "0.16s" }}>
            {t("hero_sub")}
          </p>
          <div className="fp-rise mt-10 flex flex-wrap gap-3" style={{ animationDelay: "0.24s" }}>
            <Link to="/simulasaun">
              <Button className="bg-[#C17767] hover:bg-[#A96253] text-white h-12 px-6 rounded-full shadow-lg shadow-[#C17767]/30" data-testid="home-cta-simulasaun">
                <Calculator className="w-4 h-4 mr-2" /> {t("home_cta_simulate")}
              </Button>
            </Link>
            <Link to="/auction">
              <Button variant="outline" className="border-white/30 text-white hover:bg-white/10 hover:text-white bg-white/5 backdrop-blur-sm h-12 px-6 rounded-full" data-testid="home-cta-auction">
                {t("explore_auction")} <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <a href={contact.whatsapp_link} target="_blank" rel="noopener noreferrer" data-testid="home-cta-whatsapp-hero">
              <Button className="bg-[#25D366] hover:bg-[#1EA952] text-white h-12 px-5 rounded-full">
                <MessageCircle className="w-4 h-4 mr-2" /> WhatsApp
              </Button>
            </a>
          </div>
        </div>
        <aside className="fp-rise hidden lg:block rounded-2xl border border-white/15 bg-white/10 backdrop-blur-xl p-6 shadow-2xl" style={{ animationDelay: "0.3s" }} data-testid="home-hero-card">
          <div className="text-[10px] uppercase tracking-[0.3em] text-white/60">{t("home_hero_card_title")}</div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-white/10 border border-white/10 p-4">
              <div className="text-[10px] uppercase tracking-widest text-white/60">{t("home_rate_label")}</div>
              <div className="font-display text-3xl mt-1" data-testid="home-hero-rate-range">{rateRange}</div>
            </div>
            <div className="rounded-xl bg-white/10 border border-white/10 p-4">
              <div className="text-[10px] uppercase tracking-widest text-white/60">{t("home_term_label")}</div>
              <div className="font-display text-3xl mt-1">{t("home_term_value")}</div>
            </div>
          </div>
          <ul className="mt-4 space-y-2 text-sm text-white/90">
            {["home_hero_card_1", "home_hero_card_2", "home_hero_card_3"].map((k) => (
              <li key={k} className="flex items-start gap-2"><CheckCircle2 className="w-4 h-4 mt-0.5 text-emerald-300 shrink-0" />{t(k)}</li>
            ))}
          </ul>
        </aside>
      </div>
      <div className="absolute bottom-0 inset-x-0 h-2 fp-tais opacity-90" aria-hidden />
    </section>
  );
}

function Categories({ t, img, rates }) {
  return (
    <section className="max-w-7xl mx-auto px-6 lg:px-10 mt-20 md:mt-28" data-testid="home-categories">
      <div className="max-w-2xl">
        <Eyebrow>{t("home_categories_eyebrow")}</Eyebrow>
        <H2>{t("home_categories_title")}</H2>
        <p className="mt-4 text-stone-600 text-base md:text-lg leading-relaxed">{t("home_categories_sub")}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-5 mt-10">
        {CATEGORIES.map((c) => (
          <div key={c.key} className={`group relative overflow-hidden rounded-2xl shadow-md hover:shadow-2xl transition-shadow duration-500 ${c.span}`} data-testid={`home-category-${c.key}`}>
            <img src={img(c.key)} alt="" className="absolute inset-0 w-full h-full object-cover transition-transform duration-[900ms] group-hover:scale-105" />
            <div className="absolute inset-0 bg-gradient-to-t from-[#0F1B3A]/90 via-[#0F1B3A]/30 to-transparent" />
            <div className="absolute top-4 right-4 inline-flex items-baseline gap-1 rounded-full bg-white/90 backdrop-blur px-3 py-1 text-[#1B2D5C] shadow">
              <span className="font-display text-base leading-none" data-testid={`home-rate-${c.key}`}>{rates?.[c.rateKey] ?? "—"}%</span>
              <span className="text-[10px] uppercase tracking-wider text-stone-600">/ {t("home_rate_label").split(" ").pop()}</span>
            </div>
            <div className="relative h-full flex flex-col justify-end p-5 md:p-6 text-white">
              <div className="w-10 h-10 rounded-lg bg-white/15 backdrop-blur-sm border border-white/20 flex items-center justify-center mb-3">
                <c.Icon className="w-5 h-5" />
              </div>
              <h3 className="font-display text-xl md:text-2xl leading-tight">{t(c.titleKey)}</h3>
              <p className="text-sm text-white/80 mt-2 leading-relaxed max-w-md">{t(c.bodyKey)}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Steps({ t }) {
  return (
    <section className="mt-20 md:mt-28 bg-[#1B2D5C] text-white py-16 md:py-24 relative overflow-hidden" data-testid="home-steps">
      <div className="absolute top-0 inset-x-0 h-1.5 fp-tais opacity-80" aria-hidden />
      <div className="absolute -right-32 -top-32 w-96 h-96 rounded-full bg-[#C17767]/20 blur-3xl pointer-events-none" />
      <div className="max-w-7xl mx-auto px-6 lg:px-10 relative">
        <div className="max-w-2xl">
          <div className="text-[11px] uppercase tracking-[0.28em] font-semibold text-[#F0B435] mb-3">{t("home_how_eyebrow")}</div>
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl tracking-tight leading-tight">{t("home_how_title")}</h2>
        </div>
        <ol className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative">
          <div className="hidden lg:block absolute top-7 left-[12%] right-[12%] border-t-2 border-dashed border-white/20" aria-hidden />
          {STEPS.map((s, i) => (
            <li key={i} className="relative rounded-2xl bg-white/[0.06] border border-white/10 p-6 backdrop-blur-sm hover:bg-white/[0.1] transition-colors" data-testid={`home-step-${i + 1}`}>
              <div className="flex items-center justify-between">
                <div className={`w-14 h-14 rounded-full ${s.tone} text-white flex items-center justify-center shadow-lg ring-4 ring-[#1B2D5C]`}>
                  <s.Icon className="w-6 h-6" />
                </div>
                <span className="font-display text-5xl text-white/10 leading-none select-none">{String(i + 1).padStart(2, "0")}</span>
              </div>
              <div className="text-[10px] uppercase tracking-[0.28em] text-white/50 font-semibold mt-5">{t("home_step_label")} {i + 1}</div>
              <h3 className="font-display text-xl mt-1">{t(s.titleKey)}</h3>
              <p className="text-white/75 text-sm mt-2 leading-relaxed">{t(s.bodyKey)}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Testimonials({ t, items, lang }) {
  const list = items && items.length ? items : null;
  return (
    <section className="max-w-7xl mx-auto px-6 lg:px-10 mt-20 md:mt-28" data-testid="home-testimonials">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div className="max-w-2xl">
          <Eyebrow>{t("home_testimonials_eyebrow")}</Eyebrow>
          <H2>{t("home_testimonials_title")}</H2>
        </div>
        <Link to="/review" className="inline-flex items-center gap-1 text-sm font-semibold text-[#C17767] hover:underline" data-testid="home-review-link">
          <Star className="w-4 h-4" /> {t("leave_review")}
        </Link>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 mt-10">
        {(list || TESTIMONIALS).map((tm, i) => (
          <figure key={tm.id || i} className="relative rounded-2xl border border-stone-200 bg-white p-6 md:p-7 shadow-sm hover:shadow-md transition-shadow" data-testid={`home-testimonial-${i}`}>
            <Quote className="w-8 h-8 text-[#C17767]/30 absolute top-4 right-4" />
            <blockquote className="text-stone-700 text-sm md:text-base leading-relaxed">
              &ldquo;{list ? (lang === "tet" ? tm.text_tet || tm.text_en : tm.text_en || tm.text_tet) : t(tm.textKey)}&rdquo;
            </blockquote>
            <figcaption className="mt-5 pt-4 border-t border-stone-100">
              <div className="font-display text-base text-stone-900">{list ? tm.name : t(tm.nameKey)}</div>
              <div className="text-[11px] uppercase tracking-widest text-stone-500 mt-1">{list ? (lang === "tet" ? tm.role_tet || tm.role : tm.role || tm.role_tet) : t(tm.roleKey)}</div>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

function FinalCta({ t, contact }) {
  return (
    <section className="max-w-6xl mx-auto px-6 lg:px-10 mt-20 md:mt-28" data-testid="home-final-cta">
      <div className="relative rounded-3xl bg-[#0F1B3A] text-white p-8 md:p-12 lg:p-16 overflow-hidden">
        <div className="absolute inset-y-0 left-0 w-2 fp-tais" aria-hidden />
        <div className="absolute -top-24 -right-24 w-80 h-80 rounded-full bg-[#C17767]/25 blur-3xl pointer-events-none" />
        <div className="relative flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          <div className="max-w-lg">
            <div className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.32em] text-white/60 mb-3">
              <MapPin className="w-3 h-3" /> {contact.contact_address}
            </div>
            <h2 className="font-display text-3xl md:text-4xl lg:text-5xl leading-tight">{t("cta_ready_title")}</h2>
            <p className="mt-4 text-white/80 text-sm md:text-base leading-relaxed">{t("cta_ready_sub")}</p>
          </div>
          <div className="flex flex-col sm:flex-row gap-3 shrink-0">
            <Link to="/contact">
              <Button className="bg-[#C17767] hover:bg-[#A96253] text-white h-12 px-6 rounded-full shadow-lg w-full sm:w-auto" data-testid="home-cta-contact">
                {t("contact_us")} <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <a href={contact.whatsapp_link} target="_blank" rel="noopener noreferrer" data-testid="home-cta-whatsapp">
              <Button variant="outline" className="border-white/40 text-white hover:bg-white/10 hover:text-white bg-transparent h-12 px-6 rounded-full w-full sm:w-auto">
                <MessageCircle className="w-4 h-4 mr-2" /> {contact.contact_whatsapp}
              </Button>
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
