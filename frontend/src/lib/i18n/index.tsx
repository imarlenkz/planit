"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { MESSAGES, type Locale, type MessageKey } from "./messages";

type Ctx = { locale: Locale; setLocale: (l: Locale) => void; t: (k: MessageKey, vars?: Record<string, string | number>) => string };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("kk");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("planit.locale") as Locale | null;
      if (saved && saved in MESSAGES) setLocaleState(saved);
    } catch {}
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem("planit.locale", l);
    } catch {}
  }, []);
  const t = useCallback(
    (k: MessageKey, vars?: Record<string, string | number>) => {
      let s: string = MESSAGES[locale][k] ?? MESSAGES.kk[k] ?? k;
      if (vars) for (const [name, v] of Object.entries(vars)) s = s.replace(`{${name}}`, String(v));
      return s;
    },
    [locale],
  );
  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const c = useContext(I18nContext);
  if (!c) throw new Error("useI18n outside provider");
  return c;
}
export type { MessageKey, Locale };
