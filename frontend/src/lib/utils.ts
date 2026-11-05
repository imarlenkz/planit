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
  if (p >= 85) return "bg-brand-500/85 text-white";
  if (p >= 65) return "bg-brand-100 dark:bg-brand-700/60";
  if (p >= 40) return "bg-[#c99a3b]/35 dark:bg-[#c99a3b]/45";
  return "bg-[#d9634a]/75 text-white dark:bg-[#d9634a]/60";
}

export function download(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
