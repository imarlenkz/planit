"use client";
import Link from "next/link";
import { LevelBadge } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { cn, fmt, heatBg, pctColor } from "@/lib/utils";

export function ResultsTable({ assessmentId, refreshKey }: { assessmentId: number; refreshKey?: number }) {
  const { t } = useI18n();
  const { data, loading } = useApi<any>(`/assessments/${assessmentId}/results`, [refreshKey]);
  if (loading && !data) return <Skeleton className="h-60" />;
  if (!data?.students.length) return <EmptyState title={t("common.empty")} />;
  const qs = data.questions;
  return (
    <Table>
      <THead>
        <TR>
          <TH className="w-10">№</TH>
          <TH>{t("common.student")}</TH>
          {qs.map((q: any) => <TH key={q.number} className="text-center">{q.number}<span className="block text-[10px] font-normal normal-case">/{fmt(q.max_score)}</span></TH>)}
          <TH className="text-right">{t("common.total")}</TH>
          <TH className="text-right">%</TH>
          <TH>{t("result.level")}</TH>
        </TR>
      </THead>
      <TBody>
        {data.students.map((s: any, i: number) => (
          <TR key={s.submission_id}>
            <TD className="text-muted-foreground tabular">{i + 1}</TD>
            <TD className="whitespace-nowrap">
              <Link href={`/submissions/${s.submission_id}`} className="font-medium hover:text-primary">{s.name}</Link>
              {!s.is_final ? <Badge variant="secondary" className="ml-2">{t("result.provisional")}</Badge> : null}
            </TD>
            {qs.map((q: any) => {
              const v = s.scores[q.number];
              return (
                <TD key={q.number} className="p-1 text-center">
                  <span className={cn("inline-block min-w-8 rounded px-1.5 py-0.5 text-xs font-medium tabular", heatBg(v != null ? (v / q.max_score) * 100 : null))}>{v != null ? fmt(v) : "—"}</span>
                </TD>
              );
            })}
            <TD className="text-right font-semibold tabular">{fmt(s.total)}/{fmt(s.max)}</TD>
            <TD className={`text-right font-semibold tabular ${pctColor(s.percent)}`}>{fmt(s.percent)}%</TD>
            <TD><LevelBadge level={s.level} /></TD>
          </TR>
        ))}
        <TR className="bg-muted/40 font-medium">
          <TD />
          <TD>{t("dash.avg")}</TD>
          {qs.map((q: any) => <TD key={q.number} className={`text-center text-xs tabular ${pctColor(q.percent)}`}>{fmt(q.percent, 0)}%</TD>)}
          <TD className="text-right tabular">{fmt(data.summary.avg_score)}</TD>
          <TD className={`text-right tabular ${pctColor(data.summary.avg_percent)}`}>{fmt(data.summary.avg_percent)}%</TD>
          <TD />
        </TR>
      </TBody>
    </Table>
  );
}
