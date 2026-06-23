import { useState, useMemo } from "react";
import { useLang } from "../../context/LangContext";
import { Calculator } from "lucide-react";

export default function Simulasaun() {
  const { lang } = useLang();
  const [amount, setAmount] = useState(5000);
  const [months, setMonths] = useState(2);
  const [rate, setRate] = useState(10);

  const result = useMemo(() => {
    const principal = Number(amount) || 0;
    const r = Number(rate) || 0;
    const m = Number(months) || 1;
    const interestTotal = (principal * r * m) / 100;
    const total = principal + interestTotal;
    const monthly = total / m;
    return {
      total: total.toFixed(2),
      interest: interestTotal.toFixed(2),
      received: principal.toFixed(2),
      monthly: monthly.toFixed(2),
    };
  }, [amount, months, rate]);

  const T = (en, tet) => (lang === "tet" ? tet : en);

  return (
    <section className="bg-white py-16">
      <div className="max-w-5xl mx-auto px-6 lg:px-10">
        <header className="text-center mb-10">
          <h1 className="font-display text-4xl md:text-5xl font-bold text-[#1A2A52]">
            {T("Simulate Your Loan", "Simula Ita Nia Emprestimu")}
          </h1>
          <div className="w-20 h-1 bg-[#F0B435] mx-auto mt-4 rounded-full" />
          <p className="text-stone-600 mt-4 max-w-2xl mx-auto">
            {T(
              "Fill in the details to preview how much you'll need to repay.",
              "Preenche informasaun hodi haree simulasaun montante atu selu.",
            )}
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Form */}
          <div className="rounded-2xl bg-stone-50 border border-stone-200 p-8 space-y-6">
            <div>
              <label className="block text-xs uppercase tracking-wider text-stone-500 font-semibold mb-2">
                {T("Amount (USD)", "Montante (USD)")}
              </label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                data-testid="sim-amount"
                className="w-full text-2xl font-bold text-[#1A2A52] px-4 py-3 rounded-lg border border-stone-300 focus:border-[#1A2A52] focus:ring-2 focus:ring-[#1A2A52]/20 outline-none"
              />
            </div>
            <div>
              <div className="block text-xs uppercase tracking-wider text-stone-500 font-semibold mb-2">
                {T("Duration", "Durasaun")}
              </div>
              <div className="grid grid-cols-4 gap-2">
                {[1, 2, 3, 6].map((m) => (
                  <button
                    key={m}
                    onClick={() => setMonths(m)}
                    data-testid={`sim-months-${m}`}
                    className={`py-2 px-3 rounded-md text-sm font-semibold border transition-colors ${
                      months === m
                        ? "bg-[#1A2A52] text-white border-[#1A2A52]"
                        : "bg-white text-stone-700 border-stone-300 hover:border-[#1A2A52]"
                    }`}
                  >
                    {m} {T("mo", "Fulan")}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="block text-xs uppercase tracking-wider text-stone-500 font-semibold mb-2">
                {T("Interest (%)", "Juros (%)")}
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[10, 12, 15].map((r) => (
                  <button
                    key={r}
                    onClick={() => setRate(r)}
                    data-testid={`sim-rate-${r}`}
                    className={`py-2 px-3 rounded-md text-sm font-semibold border transition-colors ${
                      rate === r
                        ? "bg-[#F0B435] text-[#1A2A52] border-[#F0B435]"
                        : "bg-white text-stone-700 border-stone-300 hover:border-[#F0B435]"
                    }`}
                  >
                    {r}%
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Result */}
          <div className="rounded-2xl bg-[#1A2A52] text-white p-8 flex flex-col justify-center space-y-4">
            <div className="flex items-center gap-2 text-[#F0B435] text-xs uppercase tracking-[0.2em] font-semibold">
              <Calculator className="w-4 h-4" /> {T("Result", "Resultadu")}
            </div>
            <Row label={T("Amount received", "Montante simu")} value={`$${result.received}`} />
            <Row label={T("Interest", "Juros")} value={`$${result.interest}`} accent />
            <div className="h-px bg-white/15" />
            <Row label={T("Total to pay", "Total atu selu")} value={`$${result.total}`} large />
            <Row label={T("Monthly payment", "Pagamento mensal")} value={`$${result.monthly}`} />
            <a
              href="https://wa.me/67078372678"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="sim-wa-cta"
              className="mt-4 inline-flex items-center justify-center gap-2 px-5 py-3 rounded-md bg-[#25D366] hover:bg-[#1EA952] text-white font-semibold transition-colors"
            >
              {T("Apply on WhatsApp", "Husu Agora (WhatsApp)")}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

function Row({ label, value, large, accent }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-sm text-white/70">{label}</span>
      <span
        className={`font-display font-bold ${
          large ? "text-3xl text-[#F0B435]" : accent ? "text-xl text-[#F0B435]" : "text-xl text-white"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
