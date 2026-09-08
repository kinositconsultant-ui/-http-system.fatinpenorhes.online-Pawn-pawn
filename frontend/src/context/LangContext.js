import { createContext, useContext, useState, useMemo } from "react";
import dict from "../lib/i18n";

const LangContext = createContext(null);

const PUBLIC_PREFIXES = ["/about", "/services", "/auction", "/warehouse", "/simulasaun", "/faq", "/contact", "/verify"];
const isPublicPath = (p) => p === "/" || PUBLIC_PREFIXES.some((x) => p.startsWith(x));

export function LangProvider({ children }) {
  // Public site is Tetum-first; the staff console stays English unless the user toggles.
  const [lang, setLang] = useState(
    () => localStorage.getItem("fp_lang") || (isPublicPath(window.location.pathname) ? "tet" : "en")
  );
  const t = useMemo(() => {
    return (key) => dict[lang]?.[key] ?? dict.en[key] ?? key;
  }, [lang]);

  const change = (next) => {
    localStorage.setItem("fp_lang", next);
    setLang(next);
  };

  return (
    <LangContext.Provider value={{ lang, setLang: change, t }}>
      {children}
    </LangContext.Provider>
  );
}
export function useLang() {
  return useContext(LangContext);
}
