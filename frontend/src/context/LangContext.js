import { createContext, useContext, useState, useMemo } from "react";
import dict from "../lib/i18n";

const LangContext = createContext(null);

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem("fp_lang") || "en");
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
