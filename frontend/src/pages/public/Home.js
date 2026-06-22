import { Link } from "react-router-dom";
import { useLang } from "../../context/LangContext";
import { Button } from "../../components/ui/button";
import { ArrowRight, ShieldCheck, Clock, FileSignature } from "lucide-react";

export default function Home() {
  const { t } = useLang();

  return (
    <div className="space-y-24 pb-20">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img
            alt=""
            src="https://images.unsplash.com/photo-1591325408953-ef9298125f96?crop=entropy&cs=srgb&fm=jpg&q=85"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#2F4F4F]/85 via-[#2F4F4F]/65 to-[#2F4F4F]/30" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 lg:px-10 py-28 md:py-36 text-white">
          <div className="text-xs uppercase tracking-[0.3em] opacity-80 mb-4">
            {t("tagline")}
          </div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-tight max-w-3xl leading-[1.05]">
            {t("hero_title")}
          </h1>
          <p className="mt-6 max-w-xl text-stone-100 text-base sm:text-lg">{t("hero_sub")}</p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link to="/auction">
              <Button
                className="bg-white text-[#2F4F4F] hover:bg-stone-100"
                data-testid="home-cta-auction"
              >
                {t("explore_auction")} <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/about">
              <Button
                variant="outline"
                className="border-white/40 text-white hover:bg-white/10 hover:text-white bg-transparent"
                data-testid="home-cta-learn"
              >
                {t("learn_more")}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="max-w-7xl mx-auto px-6 lg:px-10">
        <div className="grid md:grid-cols-3 gap-6">
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
              className="p-6 rounded-lg border border-stone-200 bg-white"
              data-testid={`home-value-${i}`}
            >
              <v.Icon className="w-7 h-7 text-[#2F4F4F]" />
              <h3 className="font-display text-xl mt-4">{v.title}</h3>
              <p className="text-stone-600 text-sm mt-2 leading-relaxed">{v.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Image strip */}
      <section className="max-w-7xl mx-auto px-6 lg:px-10">
        <div className="grid md:grid-cols-2 gap-6">
          <div className="rounded-lg overflow-hidden aspect-[4/3] bg-stone-100">
            <img
              src="https://images.pexels.com/photos/13574410/pexels-photo-13574410.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
              alt="warehouse"
              className="w-full h-full object-cover"
            />
          </div>
          <div className="rounded-lg overflow-hidden aspect-[4/3] bg-stone-100">
            <img
              src="https://images.unsplash.com/photo-1600003014755-ba31aa59c4b6?crop=entropy&cs=srgb&fm=jpg&q=85"
              alt="luxury watch"
              className="w-full h-full object-cover"
            />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-5xl mx-auto px-6 lg:px-10">
        <div className="rounded-lg bg-[#2F4F4F] text-white p-10 md:p-14 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] opacity-80 mb-2">
              Loja: Dili
            </div>
            <h2 className="font-display text-3xl md:text-4xl">
              Vizita ami nia loja, ka kontaktu ami ohin.
            </h2>
          </div>
          <Link to="/contact">
            <Button
              className="bg-[#C17767] hover:bg-[#A96253]"
              data-testid="home-cta-contact"
            >
              {t("contact_us")} <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
