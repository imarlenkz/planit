"use client";
import Link from "next/link";
import { Suspense } from "react";
import { ChooseAssessment, ScopePicker, useAssessmentParam } from "@/components/assessment-scope";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { cn, fmt, pctColor } from "@/lib/utils";

function Inner() {
  const { t } = useI18n();
  const [id, setId] = useAssessmentParam();
  const { data: a } = useApi<any>(id ? `/assessments/${id}` : null);
  const { data: an } = useApi<any>(id ? `/analytics/assessments/${id}` : null);
  const { data: objectives } = useApi<any[]>("/objectives");
  const pct = (qn: number, dn: number) => an?.descriptors?.find((d: any) => d.question_number === qn && d.number === dn)?.percent;
  const obj = (oid: number | null) => objectives?.find((o) => o.id === oid);
  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.descriptors")} description={t("desc.hint")} actions={<ScopePicker value={id} onChange={setId} />} />
      {!id ? <ChooseAssessment /> : !a ? <Skeleton className="h-96" /> : !a.questions.length ? (
        <EmptyState title={t("key.empty")} action={<Button asChild><Link href={`/assessment/${id}?tab=key`}>{t("assess.key")}</Link></Button>} />
      ) : (
        <div className="space-y-3">
          {a.questions.map((q: any) => (
            <Card key={q.id}>
              <CardHeader className="pb-2">
                <CardTitle className="flex flex-wrap items-baseline gap-2 text-base">
                  {t("common.taskN", { n: q.number })}
                  <span className="text-sm font-normal text-muted-foreground">{t(`atype.${q.answer_type}` as MessageKey)} · {fmt(q.max_score)} {t("common.score").toLowerCase()}</span>
                  {obj(q.objective_id) ? <span className="ml-auto rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{obj(q.objective_id)!.code} — {obj(q.objective_id)!.description}</span> : null}
                </CardTitle>
                <p className="text-sm text-muted-foreground">{q.text}</p>
              </CardHeader>
              <CardContent>
                {q.descriptors.length ? (
                  <ul className="space-y-2">
                    {q.descriptors.map((d: any) => {
                      const p = pct(q.number, d.number);
                      return (
                        <li key={d.id ?? d.number} className="flex items-center gap-3 text-sm">
                          <span className="w-10 shrink-0 font-mono text-xs text-muted-foreground">{q.number}.{d.number}</span>
                          <span className="flex-1">{d.text}</span>
                          <span className="w-12 shrink-0 text-right text-xs text-muted-foreground">{fmt(d.points)} б.</span>
                          <div className="hidden h-2 w-28 shrink-0 overflow-hidden rounded-full bg-muted sm:block"><div className="h-full rounded-full bg-primary" style={{ width: `${p ?? 0}%` }} /></div>
                          <span className={cn("w-12 shrink-0 text-right font-semibold tabular", pctColor(p))}>{p == null ? "—" : `${fmt(p)}%`}</span>
                        </li>
                      );
                    })}
                  </ul>
                ) : <p className="text-sm text-muted-foreground">{q.criteria || "—"}</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DescriptorsPage() {
  return <Suspense><Inner /></Suspense>;
}
