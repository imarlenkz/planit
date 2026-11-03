import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const TYPE_LABEL: Record<string, string> = { BZhB: "БЖБ", TZhB: "ТЖБ", AB: "АБ" };
export const TYPE_SLUG: Record<string, string> = { bzhb: "BZhB", tzhb: "TZhB", ab: "AB" };

export function fmt(n: number | null | undefined, digits = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number.isInteger(n) ? String(n) : n.toFixed(digits).replace(/\.0+$/, "");
}

export function pctColor(p: number | null | undefined) {
  if (p === null || p === undefined) return "text-muted-foreground";
  if (p >= 85) return "text-success";
  if (p >= 65) return "text-primary";
  if (p >= 40) return "text-warning";
  return "text-destructive";
}

export function heatBg(p: number | null | undefined) {
  if (p === null || p === undefined) return "bg-muted";
  if (p >= 85) return "bg-emerald-500/80 text-white";
  if (p >= 65) return "bg-emerald-300/70 dark:bg-emerald-700/60";
  if (p >= 40) return "bg-amber-300/70 dark:bg-amber-600/60";
  return "bg-rose-400/70 text-white dark:bg-rose-700/70";
}

export function download(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
