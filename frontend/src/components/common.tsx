"use client";
import { CheckCircle2, CircleDashed, HelpCircle, XCircle, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { TYPE_LABEL, cn, fmt } from "@/lib/utils";

export function EvalStatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const map: Record<string, { v: any; icon: any }> = {
    correct: { v: "success", icon: CheckCircle2 },
    incorrect: { v: "destructive", icon: XCircle },
    partial: { v: "warning", icon: CircleDashed },
    doubtful: { v: "secondary", icon: HelpCircle },
  };
  const m = map[status] ?? map.doubtful;
  const Icon = m.icon;
  return (
    <Badge variant={m.v}>
      <Icon className="size-3" /> {t(`status.${status}` as MessageKey)}
    </Badge>
  );
}

export function ReviewBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const v = { auto_approved: "success", medium: "default", needs_review: "warning", approved: "success", overridden: "secondary" }[status] ?? "secondary";
  return (
    <Badge variant={v as any}>
      {status === "needs_review" ? <AlertTriangle className="size-3" /> : null}
      {t(`rstatus.${status}` as MessageKey)}
    </Badge>
  );
}

export function SubmissionBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const v = { needs_review: "warning", ready: "default", approved: "success", error: "destructive", processing: "secondary" }[status] ?? "secondary";
  return <Badge variant={v as any}>{t(`sub.status.${status}` as MessageKey)}</Badge>;
}

export function TypeBadge({ type }: { type: string }) {
  const color = { BZhB: "bg-[#3a4a7a]/10 text-[#3a4a7a] dark:bg-[#3a4a7a]/30 dark:text-[#aab6e0]", TZhB: "bg-[#8e4a9e]/10 text-[#8e4a9e] dark:bg-[#8e4a9e]/25 dark:text-[#c79ad2]", AB: "bg-[#17b79a]/10 text-[#0f8a73] dark:bg-[#17b79a]/20 dark:text-[#5fd8c0]" }[type];
  return <span className={cn("rounded-md px-1.5 py-0.5 text-xs font-semibold", color)}>{TYPE_LABEL[type] ?? type}</span>;
}

export function ConfidencePill({ value }: { value: number }) {
  const tone = value >= 95 ? "text-success bg-success/10" : value >= 80 ? "text-primary bg-primary/10" : "text-warning bg-warning/15";
  return <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold tabular", tone)}>{fmt(value, 0)}%</span>;
}

export function LevelBadge({ level }: { level: string }) {
  const { t } = useI18n();
  const v = { high: "success", medium: "default", low: "warning", very_low: "destructive" }[level] ?? "secondary";
  return <Badge variant={v as any}>{t(`level.${level}` as MessageKey)}</Badge>;
}

export function AssessmentPicker({ value, onChange, className }: { value?: number; onChange: (id: number) => void; className?: string }) {
  const { t } = useI18n();
  const { data } = useApi<{ items: any[] }>("/assessments?size=200");
  return (
    <Select className={className} value={value ?? ""} onChange={(e) => onChange(Number(e.target.value))} aria-label={t("review.selectAssessment")}>
      <option value="" disabled>
        {t("review.selectAssessment")}
      </option>
      {data?.items.map((a) => (
        <option key={a.id} value={a.id}>
          {TYPE_LABEL[a.type]} · {a.class_name} · {a.title}
        </option>
      ))}
    </Select>
  );
}

export function ScoreBar({ score, max }: { score: number; max: number }) {
  const p = max ? (score / max) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full", p >= 85 ? "bg-success" : p >= 65 ? "bg-primary" : p >= 40 ? "bg-warning" : "bg-destructive")} style={{ width: `${p}%` }} />
      </div>
      <span className="tabular text-sm">
        {fmt(score)}/{fmt(max)}
      </span>
    </div>
  );
}
