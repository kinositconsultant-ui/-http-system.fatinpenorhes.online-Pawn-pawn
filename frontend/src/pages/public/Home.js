import { Link } from "react-router-dom";
import { useLang } from "../../context/LangContext";
import { Button } from "../../components/ui/button";
import {
  ArrowRight,
  ShieldCheck,
  Clock,
  FileSignature,
  Car,
  Bike,
  Smartphone,
  Truck,
  UserPlus,
  Search,
  Banknote,
  KeyRound,
  Quote,
  MessageCircle,
} from "lucide-react";

const CATEGORIES = [
  {
    key: "car",
    Icon: Car,
    titleKey: "cat_car_title",
    bodyKey: "cat_car_body",
    img: "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    tint: "from-[#1B2D5C] to-[#0F1B3A]",
  },
  {
    key: "moto",
    Icon: Bike,
    titleKey: "cat_moto_title",
    bodyKey: "cat_moto_body",
    img: "https://images.unsplash.com/photo-1558981806-ec527fa84c39?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    tint: "from-[#4A5568] to-[#1B2D5C]",
  },
  {
    key: "elek",
    Icon: Smartphone,
    titleKey: "cat_elek_title",
    bodyKey: "cat_elek_body",
    img: "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    tint: "from-[#C17767] to-[#8B5A50]",
  },
  {
    key: "pez",
    Icon: Truck,
    titleKey: "cat_pez_title",
    bodyKey: "cat_pez_body",
    img: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    tint: "from-[#0F1B3A] to-[#000000]",
  },
];

const STEPS = [
  { Icon: UserPlus, titleKey: "step1_title", bodyKey: "step1_body" },
  { Icon: Search, titleKey: "step2_title", bodyKey: "step2_body" },
  { Icon: Banknote, titleKey: "step3_title", bodyKey: "step3_body" },
  { Icon: KeyRound, titleKey: "step4_title", bodyKey: "step4_body" },
];

const TESTIMONIALS = [
  { textKey: "testim_1", nameKey: "testim_1_name", roleKey: "testim_1_role" },
  { textKey: "testim_2", nameKey: "testim_2_name", roleKey: "testim_2_role" },
  { textKey: "testim_3", nameKey: "testim_3_name", roleKey: "testim_3_role" },
];

export default function Home() {
  const { t } = useLang();

  return (
    <div className="pb-20">
      {/* ==================== HERO ==================== */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img
            alt=""
            src="https://images.unsplash.com/photo-1591325408953-ef9298125f96?crop=entropy&cs=srgb&fm=jpg&q=85"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0B1633]/90 via-[#1B2D5C]/70 to-[#1B2D5C]/25" />
          <div
            className="absolute inset-0 opacity-[0.12] mix-blend-overlay pointer-events-none"
            style={{
              backgroundImage:
                "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.55'/></svg>\")",
            }}
          />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 lg:px-10 py-24 md:py-32 lg:py-40 text-white">
          <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-white/80 mb-6 px-3 py-1 rounded-full border border-white/15 bg-white/5 backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {t("tagline")}
          </div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl xl:text-7xl tracking-tight max-w-3xl leading-[1.05]">
            {t("hero_title")}
          </h1>
          <p className="mt-6 max-w-xl text-stone-100 text-base sm:text-lg leading-relaxed">
            {t("hero_sub")}
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link to="/auction">
              <Button className="bg-white text-[#1B2D5C] hover:bg-stone-100 h-11 px-5 shadow-lg" data-testid="home-cta-auction">
                {t("explore_auction")} <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/about">
              <Button
                variant="outline"
                className="border-white/40 text-white hover:bg-white/10 hover:text-white bg-transparent h-11 px-5"
                data-testid="home-cta-learn"
              >
                {t("learn_more")}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ==================== VALUES ==================== */}
      <section className="max-w-7xl mx-auto px-6 lg:px-10 -mt-12 md:-mt-16 relative z-10">
        <div className="grid md:grid-cols-3 gap-4 md:gap-6">
          {[
            {
              Icon: ShieldCheck,
              title: "Transparent Terms",
              body: "Clear interest at 10% or 15%, no hidden fees. Every contract is signed and printed.",
            },
            {
              Icon: Clock,
              title: "Same-Day Cash",
              body: "Bring your vehicle, motorcycle or electronic and walk out with USD on the same day.",
            },
            {
              Icon: FileSignature,
              title: "Recover with Dignity",
              body: "Partial, interest-only or full payments — your terms, your timeline.",
            },
          ].map((v, i) => (
            <div
              key={i}
              className="p-6 rounded-xl border border-stone-200 bg-white shadow-sm hover:shadow-md transition-shadow"
              data-testid={`home-value-${i}`}
            >
              <div className="w-10 h-10 rounded-lg bg-[#1B2D5C]/5 border border-[#1B2D5C]/10 flex items-center justify-center">
                <v.Icon className="w-5 h-5 text-[#1B2D5C]" />
              </div>
              <h3 className="font-display text-lg md:text-xl mt-4">{v.title}</h3>
              <p className="text-stone-600 text-sm mt-2 leading-relaxed">{v.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ==================== CATEGORY MOSAIC ==================== */}
      <section className="max-w-7xl mx-auto px-6 lg:px-10 mt-20 md:mt-28">
        <div className="max-w-2xl">
          <div className="text-[11px] uppercase tracking-[0.28em] text-[#C17767] mb-3">
            {t("home_categories_eyebrow")}
          </div>
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl tracking-tight text-stone-900 leading-tight">
            {t("home_categories_title")}
          </h2>
          <p className="mt-4 text-stone-600 text-base md:text-lg leading-relaxed">
            {t("home_categories_sub")}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-5 mt-10">
          {CATEGORIES.map((c) => (
            <div
              key={c.key}
              className="group relative overflow-hidden rounded-xl aspect-[4/5] shadow-md hover:shadow-2xl transition-all duration-500"
              data-testid={`home-category-${c.key}`}
            >
              <img
                src={c.img}
                alt=""
                className="absolute inset-0 w-full h-full object-cover transition-transform duration-[900ms] group-hover:scale-110"
              />
              <div className={`absolute inset-0 bg-gradient-to-t ${c.tint} opacity-80 group-hover:opacity-90 transition-opacity`} />
              <div className="relative h-full flex flex-col justify-between p-5 text-white">
                <div className="w-10 h-10 rounded-lg bg-white/15 backdrop-blur-sm border border-white/20 flex items-center justify-center">
                  <c.Icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-display text-xl md:text-2xl leading-tight">{t(c.titleKey)}</h3>
                  <p className="text-sm text-white/80 mt-2 leading-relaxed">{t(c.bodyKey)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ==================== HOW IT WORKS (4 steps) ==================== */}
      <section className="mt-20 md:mt-28 bg-gradient-to-b from-stone-50 to-white py-16 md:py-24">
        <div className="max-w-7xl mx-auto px-6 lg:px-10">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.28em] text-[#C17767] mb-3">
              {t("home_how_eyebrow")}
            </div>
            <h2 className="font-display text-3xl md:text-4xl lg:text-5xl tracking-tight text-stone-900 leading-tight">
              {t("home_how_title")}
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 md:gap-6 mt-10 relative">
            {/* Dashed connector line (desktop only, subtle) */}
            <div className="hidden lg:block absolute top-8 left-[12.5%] right-[12.5%] h-px border-t-2 border-dashed border-stone-200 -z-0" />
            {STEPS.map((s, i) => (
              <div
                key={i}
                className="relative bg-white rounded-xl border border-stone-200 p-6 shadow-sm hover:shadow-md transition-shadow z-10"
                data-testid={`home-step-${i + 1}`}
              >
                <div className="flex items-start gap-4">
                  <div className="shrink-0 w-14 h-14 rounded-full bg-[#1B2D5C] text-white flex items-center justify-center shadow-md">
                    <s.Icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] uppercase tracking-[0.28em] text-stone-400 font-semibold">
                      Step {String(i + 1).padStart(2, "0")}
                    </div>
                    <h3 className="font-display text-lg md:text-xl mt-1 text-stone-900">
                      {t(s.titleKey)}
                    </h3>
                    <p className="text-stone-600 text-sm mt-2 leading-relaxed">
                      {t(s.bodyKey)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ==================== TESTIMONIALS ==================== */}
      <section className="max-w-7xl mx-auto px-6 lg:px-10 mt-20 md:mt-28">
        <div className="max-w-2xl">
          <div className="text-[11px] uppercase tracking-[0.28em] text-[#C17767] mb-3">
            {t("home_testimonials_eyebrow")}
          </div>
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl tracking-tight text-stone-900 leading-tight">
            {t("home_testimonials_title")}
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 mt-10">
          {TESTIMONIALS.map((tm, i) => (
            <figure
              key={i}
              className="relative rounded-xl border border-stone-200 bg-white p-6 md:p-7 shadow-sm hover:shadow-md transition-shadow"
              data-testid={`home-testimonial-${i}`}
            >
              <Quote className="w-8 h-8 text-[#C17767]/30 absolute top-4 right-4" />
              <blockquote className="text-stone-700 text-sm md:text-base leading-relaxed">
                &ldquo;{t(tm.textKey)}&rdquo;
              </blockquote>
              <figcaption className="mt-5 pt-4 border-t border-stone-100">
                <div className="font-display text-base text-stone-900">
                  {t(tm.nameKey)}
                </div>
                <div className="text-[11px] uppercase tracking-widest text-stone-500 mt-1">
                  {t(tm.roleKey)}
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* ==================== FINAL CTA ==================== */}
      <section className="max-w-6xl mx-auto px-6 lg:px-10 mt-20 md:mt-28">
        <div className="relative rounded-2xl bg-[#1B2D5C] text-white p-8 md:p-12 lg:p-16 overflow-hidden">
          {/* Decorative orbs */}
          <div className="absolute -top-24 -right-24 w-80 h-80 rounded-full bg-[#C17767]/20 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-32 -left-24 w-96 h-96 rounded-full bg-[#0F1B3A]/60 blur-3xl pointer-events-none" />
          <div className="relative flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
            <div className="max-w-lg">
              <div className="text-[10px] uppercase tracking-[0.32em] text-white/60 mb-3">
                Loja: Caicoli, Dili
              </div>
              <h2 className="font-display text-3xl md:text-4xl lg:text-5xl leading-tight">
                {t("cta_ready_title")}
              </h2>
              <p className="mt-4 text-white/80 text-sm md:text-base leading-relaxed">
                {t("cta_ready_sub")}
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3 shrink-0">
              <Link to="/contact">
                <Button
                  className="bg-[#C17767] hover:bg-[#A96253] text-white h-11 px-5 shadow-lg w-full sm:w-auto"
                  data-testid="home-cta-contact"
                >
                  {t("contact_us")} <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <a
                href="https://wa.me/67078372678"
                target="_blank"
                rel="noopener noreferrer"
                data-testid="home-cta-whatsapp"
              >
                <Button
                  variant="outline"
                  className="border-white/40 text-white hover:bg-white/10 hover:text-white bg-transparent h-11 px-5 w-full sm:w-auto"
                >
                  <MessageCircle className="w-4 h-4 mr-2" /> WhatsApp
                </Button>
              </a>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
