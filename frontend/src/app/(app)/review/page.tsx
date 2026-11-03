"use client";
import { AlertTriangle, ArrowRight } from "lucide-react";
import Link from "next/link";
import { Suspense, useState } from "react";
import { ChooseAssessment, ScopePicker, useAssessmentParam } from "@/components/assessment-scope";
import { ConfidencePill, EvalStatusBadge, ReviewBadge } from "@/components/common";
import { BatchActions, SubmissionsTable } from "@/components/submissions-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { fmt } from "@/lib/utils";

function Queue({ assessmentId, rk, onDone }: { assessmentId: number; rk: number; onDone: () => void }) {
  const { t } = useI18n();
  const [medium, setMedium] = useState(false);
  const { data, error, loading, reload } = useApi<any[]>(`/review/queue?assessment_id=${assessmentId}&include_medium=${medium}`, [rk]);
  if (error) return <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} />;
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="size-5 text-warning" /> {t("review.queue", { n: data?.length ?? 0 })}
        </CardTitle>
        <div className="flex flex-wrap items-center gap-3">
          <Switch checked={medium} onChange={setMedium} label={t("review.includeMedium")} />
          <BatchActions assessmentId={assessmentId} onDone={() => { reload(); onDone(); }} />
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {loading && !data ? (
          <div className="p-4"><Skeleton className="h-40" /></div>
        ) : !data?.length ? (
          <EmptyState title={t("review.nothing")} />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>{t("common.student")}</TH>
                  <TH>{t("review.question")}</TH>
                  <TH>{t("review.studentAnswer")}</TH>
                  <TH>{t("common.score")}</TH>
                  <TH>{t("review.confidence")}</TH>
                  <TH>{t("common.status")}</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {data.map((r) => (
                  <TR key={r.evaluation_id}>
                    <TD className="font-medium">{r.student_name ?? <span className="text-warning">{t("sub.unknown")}</span>}</TD>
                    <TD className="tabular">{r.question_number}</TD>
                    <TD className="max-w-[280px]">
                      <p className="truncate font-mono text-sm">{r.detected_answer || "—"}</p>
                      <p className="truncate text-xs text-muted-foreground">{r.expected_answer}</p>
                    </TD>
                    <TD className="tabular">{fmt(r.score)}/{fmt(r.max_score)}</TD>
                    <TD><ConfidencePill value={r.confidence} /></TD>
                    <TD><div className="flex flex-wrap gap-1"><EvalStatusBadge status={r.status} /><ReviewBadge status={r.review_status} /></div></TD>
                    <TD className="text-right">
                      <Button size="sm" variant="outline" asChild>
                        <Link href={`/submissions/${r.submission_id}?q=${r.question_number}`}>{t("review.openWork")} <ArrowRight /></Link>
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ReviewInner() {
  const { t } = useI18n();
  const [id, setId] = useAssessmentParam();
  const [rk, setRk] = useState(0);
  return (
    <div className="space-y-6">
      <PageHeader title={t("review.title")} actions={<ScopePicker value={id} onChange={setId} />} />
      {!id ? (
        <ChooseAssessment />
      ) : (
        <>
          <Queue assessmentId={id} rk={rk} onDone={() => setRk((x) => x + 1)} />
          <SubmissionsTable assessmentId={id} refreshKey={rk} />
        </>
      )}
    </div>
  );
}

export default function ReviewPage() {
  return <Suspense><ReviewInner /></Suspense>;
}
