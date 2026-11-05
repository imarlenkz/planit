"use client";
import {
  BarChart3, BookOpen, ClipboardCheck, FileSpreadsheet, FileText, GraduationCap, Layers, LayoutDashboard, ListChecks, LogOut,
  Menu, Monitor, Moon, NotebookPen, School, Settings, Sun, Trophy, Users, X, Languages, Library,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown";
import { isStaff, useAuth } from "@/lib/auth";
import { useI18n, type MessageKey, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Item = { href: string; key: MessageKey; icon: any };
const STAFF_NAV: { group: MessageKey; items: Item[] }[] = [
  {
    group: "nav.group.work",
    items: [
      { href: "/dashboard", key: "nav.dashboard", icon: LayoutDashboard },
      { href: "/classes", key: "nav.classes", icon: School },
      { href: "/students", key: "nav.students", icon: Users },
    ],
  },
  {
    group: "nav.group.assessments",
    items: [
      { href: "/assessments/bzhb", key: "nav.bzhb", icon: FileText },
      { href: "/assessments/tzhb", key: "nav.tzhb", icon: NotebookPen },
      { href: "/assessments/ab", key: "nav.ab", icon: Layers },
      { href: "/review", key: "nav.review", icon: ClipboardCheck },
      { href: "/results", key: "nav.results", icon: Trophy },
      { href: "/analytics", key: "nav.analytics", icon: BarChart3 },
      { href: "/reports", key: "nav.reports", icon: FileSpreadsheet },
    ],
  },
  {
    group: "nav.group.library",
    items: [
      { href: "/question-bank", key: "nav.bank", icon: Library },
      { href: "/descriptors", key: "nav.descriptors", icon: ListChecks },
      { href: "/subjects", key: "nav.subjects", icon: BookOpen },
      { href: "/settings", key: "nav.settings", icon: Settings },
    ],
  },
];
const STUDENT_NAV = [{ group: "nav.group.work" as MessageKey, items: [
  { href: "/me", key: "nav.myResults" as MessageKey, icon: GraduationCap },
  { href: "/settings", key: "nav.settings" as MessageKey, icon: Settings },
] }];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const path = usePathname();
  const nav = isStaff(user) ? STAFF_NAV : STUDENT_NAV;
  return (
    <nav className="flex flex-col gap-5 px-3 py-4">
      {nav.map((g) => (
        <div key={g.group} className="space-y-1">
          <p className="font-mono-label px-3 pb-1 text-[10.5px] text-brand-700 dark:text-brand-400">{t(g.group)}</p>
          {g.items.map((it) => {
            const active = path === it.href || path.startsWith(it.href + "/");
            const Icon = it.icon;
            return (
              <Link
                key={it.href}
                href={it.href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-3 rounded-[13px] px-3 py-2.5 text-sm font-semibold transition-colors",
                  active
                    ? "bg-sidebar-active text-sidebar-active-foreground shadow-sm"
                    : "text-sidebar-foreground/55 hover:bg-foreground/5 hover:text-sidebar-foreground",
                )}
              >
                <Icon className="size-4 shrink-0" />
                <span className="truncate">{t(it.key)}</span>
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const { t, locale, setLocale } = useI18n();
  const { setTheme } = useTheme();
  if (!user) return null;
  const initials = user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 rounded-full p-0.5 pr-2 hover:bg-accent" aria-label="User menu">
          <span className="grid size-8 place-items-center rounded-full bg-brand-500 text-xs font-bold text-white">{initials}</span>
          <span className="hidden text-left leading-tight md:block">
            <span className="block max-w-[160px] truncate text-sm font-medium">{user.full_name}</span>
            <span className="block text-xs text-muted-foreground">{t(`role.${user.role}` as MessageKey)}</span>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60">
        <DropdownMenuLabel>{user.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{t("set.language")}</DropdownMenuLabel>
        {(["kk", "ru", "en"] as Locale[]).map((l) => (
          <DropdownMenuItem key={l} onSelect={() => setLocale(l)} className={locale === l ? "font-semibold text-primary" : ""}>
            <Languages /> {{ kk: "Қазақша", ru: "Русский", en: "English" }[l]}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => setTheme("light")}><Sun /> {t("theme.light")}</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("dark")}><Moon /> {t("theme.dark")}</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("system")}><Monitor /> {t("theme.system")}</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={logout} className="text-destructive"><LogOut /> {t("auth.logout")}</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <Button variant="ghost" size="icon" aria-label="Theme" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
      {mounted && resolvedTheme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(path)}`);
    if (!loading && user?.role === "student" && !["/me", "/settings"].some((p) => path.startsWith(p)) && !path.startsWith("/submissions")) router.replace("/me");
  }, [loading, user, path]);
  useEffect(() => setOpen(false), [path]);

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="flex items-center gap-3 text-muted-foreground">
          <span className="size-5 animate-spin rounded-full border-2 border-primary border-r-transparent" /> {t("common.loading")}
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r bg-sidebar lg:flex">
        <div className="flex h-16 items-center border-b px-5">
          <Logo />
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <NavLinks />
        </div>
        <div className="border-t p-4 text-xs text-muted-foreground">
          <p className="font-mono-label mb-1 text-[10px] text-muted-foreground/70">{t("auth.school")}</p>
          <p className="truncate font-semibold text-foreground/80">{user.school_name ?? t("app.tagline")}</p>
        </div>
      </aside>
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-sidebar shadow-xl">
            <div className="flex h-16 items-center justify-between border-b px-5">
              <Logo />
              <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close menu"><X /></Button>
            </div>
            <div className="flex-1 overflow-y-auto"><NavLinks onNavigate={() => setOpen(false)} /></div>
          </aside>
        </div>
      ) : null}
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur md:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label="Menu"><Menu /></Button>
          <div className="lg:hidden"><Logo /></div>
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <main className="mx-auto w-full min-w-0 max-w-[1400px] flex-1 px-4 py-6 md:px-6 md:py-8">{children}</main>
      </div>
    </div>
  );
}

