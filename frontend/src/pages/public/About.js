import { useLang } from "../../context/LangContext";

export default function About() {
  const { t } = useLang();
  return (
    <div className="max-w-4xl mx-auto px-6 lg:px-10 py-20 space-y-10" data-testid="about-root">
      <header>
        <div className="text-eyebrow">{t("about")}</div>
        <h1 className="font-display text-4xl sm:text-5xl mt-1">FATIN PENHORES UNIPESSOAL, LDA</h1>
        <p className="text-sm text-stone-500 mt-2">Caicoli, Dili · WhatsApp: +670 78372678 · fatinpenhores@gmail.com</p>
      </header>
      <div className="prose prose-stone max-w-none">
        <p className="text-stone-700 leading-relaxed text-lg">
          Fatin Penhores is a trusted pawn and auction house in Dili, Timor-Leste. We
          provide short-term loans against vehicles, motorcycles and electronics — every
          contract transparent, every receipt printed, every term respected.
        </p>
        <p className="text-stone-700 leading-relaxed">
          We accept Bilhete de Identidade (BI), Electoral Card and Passport for client
          registration. Our standard interest rates are 10% and 15%, with full, partial and
          interest-only payment options. When contracts expire, items move to our public
          auction so the local community has first access at fair starting prices.
        </p>
      </div>
      <div className="grid sm:grid-cols-3 gap-6 pt-8">
        {[
          ["Loan tiers", "USD 100 — 10,000+"],
          ["Interest options", "10% or 15%"],
          ["Coverage", "Dili & surroundings"],
        ].map(([k, v]) => (
          <div key={k} className="p-5 rounded-lg border border-stone-200 bg-white">
            <div className="text-eyebrow">{k}</div>
            <div className="font-display text-2xl mt-1">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
