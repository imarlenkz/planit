"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AssessmentPicker } from "@/components/common";
import { EmptyState } from "@/components/ui/misc";
import { useI18n } from "@/lib/i18n";
import { ClipboardList } from "lucide-react";

/** Reads ?assessment=<id> and renders a picker that keeps it in the URL. */
export function useAssessmentParam() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = params.get("assessment");
  const id = raw ? Number(raw) : undefined;
  const set = (v: number) => router.replace(`${pathname}?assessment=${v}`);
  return [id, set] as const;
}

export function ScopePicker({ value, onChange }: { value?: number; onChange: (id: number) => void }) {
  return <AssessmentPicker value={value} onChange={onChange} className="w-full sm:w-[420px]" />;
}

export function ChooseAssessment() {
  const { t } = useI18n();
  return <EmptyState icon={ClipboardList} title={t("review.selectAssessment")} hint={t("common.chooseHint")} />;
}
