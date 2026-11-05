"use client";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Suspense, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useI18n, type Locale, type MessageKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const DEMO = [
  ["teacher@planit.kz", "role.teacher"],
  ["director@planit.kz", "role.school_admin"],
  ["admin@planit.kz", "role.admin"],
  ["student@planit.kz", "role.student"],
] as const;
const SSO_ERRORS = ["school", "conflict", "disabled", "role", "state", "denied", "off", "error"];

const GRID_BACKDROP: CSSProperties = {
  backgroundImage:
    "linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)",
  backgroundSize: "120px 90px",
};
const STAR_COLORS = ["#ffffff", "#57bb92", "#8fd6b6", "#ffffff"];

// deterministic field, so the hero does not reshuffle between renders
function buildStars(count: number) {
  return Array.from({ length: count }, (_, i) => {
    const seed = i * 61.87 + 19;
    const rand = (n: number) => Math.sin(seed * n) * 0.5 + 0.5;
    return {
      id: i, left: rand(1) * 100, top: rand(2) * 100, size: 2 + rand(3) * 3, sx: rand(4) * 40 - 20, sy: rand(5) * 40 - 20,
      color: STAR_COLORS[i % STAR_COLORS.length], duration: 2.5 + rand(6) * 3, delay: -rand(7) * 5,
    };
  });
}

function Mark() {
  return (
    <span className="flex items-center gap-2.5">
      <svg viewBox="0 0 36 36" className="size-9" aria-hidden>
        <rect width="36" height="36" rx="13" fill="#2f9e6e" />
        <path d="M10.5 19.2l4.6 4.6L25.5 13" fill="none" stroke="white" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-display text-lg font-bold text-white">Planit</span>
    </span>
  );
}

const fieldCls =
  "mt-1.5 block h-[42px] w-full rounded-[10px] border border-white/14 bg-white/[.03] px-3 text-sm text-white placeholder:text-white/30 focus:border-brand-500 focus:bg-white/[.06] focus:outline-none focus:ring-[3px] focus:ring-brand-500/20";

function LoginForm() {
  const { login } = useAuth();
  const { t, locale, setLocale } = useI18n();
  const { resolvedTheme, setTheme } = useTheme();
  const router = useRouter();
  const params = useSearchParams();
  const stars = useMemo(() => buildStars(140), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ enabled: boolean; demo: boolean } | null>(null);
  const [mounted, setMounted] = useState(false);
  const ssoCode = params.get("sso") ?? "";
  const ssoError = SSO_ERRORS.includes(ssoCode) ? t(`sso.${ssoCode}` as MessageKey) : null;

  useEffect(() => {
    setMounted(true);
    fetch("/api/auth/sso/status", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        setStatus(s ?? { enabled: false, demo: false });
        if (s?.demo) {
          setEmail((e) => e || "teacher@planit.kz");
          setPassword((p) => p || "demo12345");
        }
      })
      .catch(() => setStatus({ enabled: false, demo: false }));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(email, password);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : u.role === "student" ? "/me" : "/dashboard");
    } catch (err: any) {
      toast.error(err?.message || t("auth.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-surface-900">
      <div className="relative hidden flex-1 overflow-hidden lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="pointer-events-none absolute inset-0" style={GRID_BACKDROP} />
        <div className="pointer-events-none absolute -left-24 -top-24 size-96 rounded-full bg-brand-500/20 blur-[90px]" />
        <div className="pointer-events-none absolute inset-0 overflow-hidden" style={{ perspective: "400px" }}>
          {stars.map((s) => (
            <div
              key={s.id}
              className="animate-star-fly absolute rounded-full"
              style={{
                left: `${s.left}%`, top: `${s.top}%`, width: s.size, height: s.size, backgroundColor: s.color,
                animationDuration: `${s.duration}s`, animationDelay: `${s.delay}s`, "--sx": `${s.sx}px`, "--sy": `${s.sy}px`,
              } as CSSProperties}
            />
          ))}
        </div>
        <div className="relative"><Mark /></div>
        <div className="relative max-w-lg">
          <p className="font-mono-label text-[10.5px] text-brand-400">{t("auth.eyebrow")}</p>
          <h2 className="mt-3 font-display text-[46px] font-bold leading-[1.05] tracking-[-0.02em] text-white">{t("auth.headline")}</h2>
          <p className="mt-4 text-[17px] leading-relaxed text-white/50">{t("app.tagline")}</p>
          <ul className="mt-8 space-y-3 text-white/75">
            {(["dash.flow3", "dash.flow4", "dash.flow5"] as const).map((k, i) => (
              <li key={k} className="flex items-center gap-3">
                <span className="grid size-7 place-items-center rounded-full bg-brand-500/20 font-mono text-xs font-medium text-brand-400">{i + 1}</span>
                {t(k)}
              </li>
            ))}
          </ul>
        </div>
        <p className="font-mono-label relative text-[10px] text-white/30">© Planit · iMARLEN</p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 lg:max-w-[560px]">
        <div className="mb-5 flex w-full max-w-[380px] items-center justify-between">
          <span className="lg:invisible"><Mark /></span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Theme"
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              className="grid size-8 place-items-center rounded-full text-white/60 transition-colors hover:bg-white/10 hover:text-white"
            >
              {mounted && resolvedTheme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
            <div className="flex gap-0.5 rounded-full border border-white/14 p-0.5 text-xs">
              {(["kk", "ru", "en"] as Locale[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLocale(l)}
                  className={cn("rounded-full px-2.5 py-1 font-semibold uppercase text-white/55 hover:text-white", locale === l && "bg-brand-500 text-white")}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="animate-fade-in-up w-full max-w-[380px] rounded-[20px] bg-surface-800 p-8" style={{ boxShadow: "0 24px 60px rgba(0,0,0,.4)" }}>
          <h1 className="font-display text-2xl font-bold text-white">{t("auth.welcome")}</h1>
          <p className="mt-1 text-sm text-white/50">{t("auth.subtitle")}</p>

          {ssoError && (
            <div role="alert" className="mt-5 rounded-lg border border-[#d9634a]/40 bg-[#d9634a]/12 px-3 py-2 text-sm text-[#ef8f76]">
              {ssoError}
            </div>
          )}

          {status?.enabled && (
            <>
              <a
                href="/api/auth/sso/login"
                className="mt-7 flex h-11 w-full items-center justify-center gap-2 rounded-full bg-brand-500 px-3 text-sm font-bold text-white transition-colors hover:bg-brand-600"
              >
                <span className="grid size-5 place-items-center rounded-md bg-white/20 font-display text-[11px] font-extrabold">iD</span>
                {t("auth.sso")}
              </a>
              <p className="mt-4 text-center text-xs text-white/40">{t("auth.ssoOr")}</p>
            </>
          )}

          <form onSubmit={submit} className={cn("space-y-4", status?.enabled ? "mt-4" : "mt-7")}>
            <div>
              <label htmlFor="email" className="text-xs font-semibold text-white/60">{t("auth.email")}</label>
              <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required className={fieldCls} />
            </div>
            <div>
              <label htmlFor="password" className="text-xs font-semibold text-white/60">{t("auth.password")}</label>
              <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required className={fieldCls} />
            </div>
            <Button
              type="submit"
              size="lg"
              loading={busy}
              className={cn("w-full font-bold", status?.enabled && "border border-white/14 bg-white/[.04] text-white hover:bg-white/10")}
            >
              {t("auth.login")}
            </Button>
          </form>

          {status?.demo && (
            <div className="mt-6 space-y-2 rounded-xl border border-white/10 bg-white/[.03] p-3">
              <p className="font-mono-label text-[10px] text-brand-400">{t("auth.demo")} · demo12345</p>
              <div className="grid grid-cols-2 gap-2">
                {DEMO.map(([e, r]) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => { setEmail(e); setPassword("demo12345"); }}
                    className={cn("rounded-lg border px-2 py-1.5 text-left text-xs transition-colors hover:border-brand-500",
                      email === e ? "border-brand-500 bg-brand-500/10" : "border-white/10")}
                  >
                    <span className="block font-semibold text-white">{t(r)}</span>
                    <span className="block truncate text-white/45">{e}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
