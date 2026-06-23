import { useState } from "react";
import { useLang } from "../../context/LangContext";
import { ChevronDown } from "lucide-react";

const QA = [
  {
    qEn: "How much interest will I be charged on my collateral?",
    qTet: "Sei kona juros hira ba sasan garantidu?",
    aEn: "It depends on the amount, duration and type of collateral. Typically rates range from 10% to 15%.",
    aTet: "Depende ba montante, durasaun no tipo garantia. Normalmente taxa husi 10% to 15%.",
  },
  {
    qEn: "How long does the process take?",
    qTet: "Prosesu dura tempu hira?",
    aEn: "Most loan applications complete between 1 and 24 hours.",
    aTet: "Normalmente prosesu bele remata entre oras 1 to 24 oras.",
  },
  {
    qEn: "Is my collateral kept secure?",
    qTet: "Garantia sei seguradu ka lae?",
    aEn: "Yes, we guarantee full security for items kept as collateral.",
    aTet: "Sim, ami garante seguransa total ba sasan garantia kliente nian.",
  },
  {
    qEn: "Can I pay before the due date?",
    qTet: "Bele selu antes tempu?",
    aEn: "Yes, with specific conditions defined in the contract.",
    aTet: "Bele, ho kondisaun espesifiku tuir kontratu.",
  },
  {
    qEn: "What documents do I need?",
    qTet: "Dokumentu saida mak presiza?",
    aEn: "A valid ID (BI / Electoral / Passport), your phone number, and ownership documents of the collateral.",
    aTet: "BI / Eleitorál / Pasaporte válidu, númeru telemovel, no dokumentu sasan garantia nian.",
  },
];

export default function FAQ() {
  const { lang } = useLang();
  const [open, setOpen] = useState(0);
  return (
    <section className="bg-white py-16">
      <div className="max-w-3xl mx-auto px-6 lg:px-10">
        <header className="text-center mb-10">
          <h1 className="font-display text-4xl md:text-5xl font-bold text-[#1A2A52]">FAQ</h1>
          <div className="w-20 h-1 bg-[#F0B435] mx-auto mt-4 rounded-full" />
        </header>
        <div className="space-y-3">
          {QA.map((qa, i) => {
            const isOpen = open === i;
            return (
              <div
                key={i}
                className={`rounded-lg border transition-colors ${
                  isOpen ? "border-[#F0B435] bg-[#F0B435]/5" : "border-stone-200 bg-white"
                }`}
                data-testid={`faq-item-${i}`}
              >
                <button
                  onClick={() => setOpen(isOpen ? -1 : i)}
                  className="w-full flex items-center justify-between gap-4 text-left px-5 py-4"
                >
                  <span className="font-display text-lg font-semibold text-[#1A2A52]">
                    {lang === "tet" ? qa.qTet : qa.qEn}
                  </span>
                  <ChevronDown
                    className={`w-5 h-5 text-[#1A2A52] transition-transform ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 text-stone-600 leading-relaxed">
                    {lang === "tet" ? qa.aTet : qa.aEn}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
