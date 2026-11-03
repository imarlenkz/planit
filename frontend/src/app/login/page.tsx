"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { useI18n, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const DEMO = [
  ["teacher@planit.kz", "role.teacher"],
  ["director@planit.kz", "role.school_admin"],
  ["admin@planit.kz", "role.admin"],
  ["student@planit.kz", "role.student"],
] as const;

function LoginForm() {
  const { login } = useAuth();
  const { t, locale, setLocale } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("teacher@planit.kz");
  const [password, setPassword] = useState("demo12345");
  const [busy, setBusy] = useState(false);

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
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-primary to-indigo-700 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <Logo className="[&_rect]:fill-white/20" />
        <div className="space-y-6">
          <h1 className="max-w-md text-4xl font-semibold leading-tight">{t("app.tagline")}</h1>
          <ul className="space-y-3 text-white/85">
            {(["dash.flow3", "dash.flow4", "dash.flow5"] as const).map((k, i) => (
              <li key={k} className="flex items-center gap-3">
                <span className="grid size-7 place-items-center rounded-full bg-white/15 text-sm font-semibold">{i + 1}</span>
                {t(k)}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-white/60">© Planit</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-8">
          <div className="flex items-center justify-between lg:justify-end">
            <Logo className="lg:hidden" />
            <div className="flex gap-1 rounded-md border p-0.5 text-xs">
              {(["kk", "ru", "en"] as Locale[]).map((l) => (
                <button key={l} onClick={() => setLocale(l)} className={cn("rounded px-2 py-1 uppercase", locale === l && "bg-primary text-primary-foreground")}>
                  {l}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold">{t("auth.welcome")}</h2>
            <p className="text-sm text-muted-foreground">{t("auth.subtitle")}</p>
          </div>
          <form onSubmit={submit} className="space-y-4">
            <Field label={t("auth.email")}>
              <Input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            <Field label={t("auth.password")}>
              <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </Field>
            <Button type="submit" className="w-full" size="lg" loading={busy}>
              {t("auth.login")}
            </Button>
          </form>
          <div className="space-y-2 rounded-lg border bg-muted/40 p-4">
            <p className="text-xs font-medium text-muted-foreground">{t("auth.demo")} · demo12345</p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO.map(([e, r]) => (
                <button key={e} type="button" onClick={() => { setEmail(e); setPassword("demo12345"); }} className="rounded-md border bg-card px-2 py-1.5 text-left text-xs hover:border-primary">
                  <span className="block font-medium">{t(r)}</span>
                  <span className="block truncate text-muted-foreground">{e}</span>
                </button>
              ))}
            </div>
          </div>
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
