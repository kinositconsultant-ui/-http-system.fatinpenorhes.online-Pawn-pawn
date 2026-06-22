import { useLang } from "../context/LangContext";

export default function LangToggle() {
  const { lang, setLang } = useLang();
  return (
    <div
      className="inline-flex items-center rounded-full border border-stone-200 bg-white p-0.5 text-xs"
      data-testid="lang-toggle"
    >
      <button
        type="button"
        onClick={() => setLang("en")}
        data-testid="lang-en"
        className={`px-3 py-1 rounded-full transition ${
          lang === "en" ? "bg-[#2F4F4F] text-white" : "text-stone-600"
        }`}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setLang("tet")}
        data-testid="lang-tet"
        className={`px-3 py-1 rounded-full transition ${
          lang === "tet" ? "bg-[#2F4F4F] text-white" : "text-stone-600"
        }`}
      >
        TET
      </button>
    </div>
  );
}
