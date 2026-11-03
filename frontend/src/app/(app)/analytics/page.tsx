"use client";
import { AlertTriangle, Award, BarChart3, Percent, Sparkles, Target, TrendingUp, Users } from "lucide-react";
import Link from "next/link";
import { Suspense, useState } from "react";
import { ChooseAssessment, ScopePicker, useAssessmentParam } from "@/components/assessment-scope";
import { HBars, PercentBars, TrendLine } from "@/components/charts";
import { TypeBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, PageHeader, Skeleton, Stat } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { cn, fmt, heatBg, pctColor } from "@/lib/utils";

const MARK_TONE: Record<string, string> = { "5": "hsl(var(--success))", "4": "hsl(var(--primary))", "3": "hsl(var(--warning))", "2": "hsl(var(--destructive))" };

function Heatmap({ heat }: { heat: { questions: number[]; rows: { name: string; cells: (number | null)[] }[] } }) {
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <table className="w-full border-separate border-spacing-0.5 text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 bg-card px-2 text-left font-medium text-muted-foreground" />
            {heat.questions.map((q) => <th key={q} className="w-10 px-1 py-1 font-medium tabular text-muted-foreground">{q}</th>)}
          </tr>
        </thead>
        <tbody>
          {heat.rows.map((r) => (
            <tr key={r.name}>
              <td className="sticky left-0 whitespace-nowrap bg-card pr-3 font-medium">{r.name}</td>
              {r.cells.map((c, i) => (
                <td key={i} title={`${r.name} · ${heat.questions[i]}: ${fmt(c)}%`} className={cn("h-7 rounded-sm text-center tabular", heatBg(c))}>{c == null ? "" : Math.round(c)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Inner() {
  const { t } = useI18n();
  const [id, setId] = useAssessmentParam();
  const { data: d, error, loading, reload } = useApi<any>(id ? `/analytics/assessments/${id}` : null);
  const { data: dyn } = useApi<any[]>(d?.assessment?.class_id ? `/analytics/classes/${d.assessment.class_id}/dynamics` : null, [d?.assessment?.class_id]);
  const [tableView, setTableView] = useState(false);

  const header = <PageHeader title={t("an.title")} actions={<ScopePicker value={id} onChange={setId} />} />;
  if (!id) return <div className="space-y-6">{header}<ChooseAssessment /></div>;
  if (error) return <div className="space-y-6">{header}<ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} /></div>;
  if (loading || !d) return <div className="space-y-6">{header}<Skeleton className="h-96" /></div>;

  const s = d.summary;
  const marks = ["5", "4", "3", "2"].map((m) => ({ mark: m, count: s.marks?.[m] ?? 0 }));
  const q = d.questions.map((x: any) => ({ ...x, label: `${x.number}` }));
  const desc = d.descriptors.map((x: any) => ({ label: x.label, percent: x.percent, full: `${x.label} ${x.text}` }));
  const obj = d.objectives.map((x: any) => ({ label: x.code, percent: x.percent, full: `${x.code} ${x.description}` }));
  const errs = d.errors.map((x: any) => ({ label: x.label, count: x.count, full: x.label }));
  const g = d.gender ?? {};

  return (
    <div className="space-y-6">
      {header}
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <TypeBadge type={d.assessment.type} /> <b className="text-foreground">{d.assessment.title}</b> · {d.assessment.class_name} · {d.assessment.subject} · {d.assessment.date}
        <Button variant="link" size="sm" asChild className="ml-auto"><Link href={`/assessment/${id}?tab=results`}>{t("nav.results")} →</Link></Button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label={t("an.submitted")} value={`${s.submitted}/${s.students_total}`} icon={Users} />
        <Stat label={t("an.avgScore")} value={`${fmt(s.avg_score)} / ${fmt(s.max_score)}`} icon={BarChart3} />
        <Stat label={t("an.avgPercent")} value={<span className={pctColor(s.avg_percent)}>{fmt(s.avg_percent)}%</span>} icon={Percent} />
        <Stat label={`${t("an.max")} / ${t("an.min")}`} value={`${fmt(s.max_percent)}% / ${fmt(s.min_percent)}%`} icon={TrendingUp} />
        <Stat label={t("an.success")} value={`${fmt(s.success_rate)}%`} icon={Target} tone="success" />
        <Stat label={t("an.quality")} value={`${fmt(s.quality_rate)}%`} icon={Award} tone="primary" />
      </div>

      {d.insights?.length ? (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-base"><Sparkles className="size-4 text-primary" /> {t("an.insights")}</CardTitle></CardHeader>
          <CardContent className="space-y-1.5 text-sm">
            {d.insights.map((x: string, i: number) => <p key={i}>• {x}</p>)}
            {d.main_problem ? <p className="flex items-start gap-1.5 pt-1 font-medium text-warning"><AlertTriangle className="mt-0.5 size-4 shrink-0" /> {t("an.mainProblem")}: {d.main_problem}</p> : null}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-start justify-between gap-2">
            <div>
              <CardTitle>{t("an.byTask")}</CardTitle>
              {d.hardest_question ? <CardDescription>{t("an.hardest")}: {t("common.taskN", { n: d.hardest_question.number })} ({fmt(d.hardest_question.percent)}%)</CardDescription> : null}
            </div>
            <Button variant="ghost" size="sm" onClick={() => setTableView((v) => !v)}>{t("an.table")}</Button>
          </CardHeader>
          <CardContent>
            {tableView ? (
              <Table>
                <THead><TR><TH>№</TH><TH>{t("key.objective")}</TH><TH>{t("dash.avg")}</TH><TH>%</TH><TH>{t("status.correct")}</TH><TH>{t("status.partial")}</TH><TH>{t("status.incorrect")}</TH></TR></THead>
                <TBody>
                  {d.questions.map((x: any) => (
                    <TR key={x.question_id}><TD>{x.number}</TD><TD>{x.objective ?? "—"}</TD><TD className="tabular">{fmt(x.avg_score)}/{fmt(x.max_score)}</TD><TD className={cn("tabular font-semibold", pctColor(x.percent))}>{fmt(x.percent)}%</TD><TD className="tabular">{x.correct}</TD><TD className="tabular">{x.partial}</TD><TD className="tabular">{x.incorrect}</TD></TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <PercentBars data={q} x="label" y="percent" name={t("common.percent")} labelFmt={(l) => t("common.taskN", { n: l })} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("an.marks")}</CardTitle></CardHeader>
          <CardContent>
            <PercentBars data={marks} x="mark" y="count" name={t("common.count")} unit="" max="auto" colorFor={(m) => MARK_TONE[m.mark]} labelFmt={(l) => `«${l}»`} />
            <div className="mt-2 grid grid-cols-4 gap-1 text-center text-xs">
              {marks.map((m) => <div key={m.mark}><b className="text-base tabular">{m.count}</b><p className="text-muted-foreground">«{m.mark}»</p></div>)}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>{t("an.descriptors")}</CardTitle></CardHeader>
          <CardContent>{desc.length ? <HBars data={desc} label="label" value="percent" /> : <p className="text-sm text-muted-foreground">—</p>}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("an.objectives")}</CardTitle></CardHeader>
          <CardContent>{obj.length ? <HBars data={obj} label="label" value="percent" /> : <p className="text-sm text-muted-foreground">—</p>}</CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>{t("an.errors")}</CardTitle></CardHeader>
          <CardContent>{errs.length ? <HBars data={errs} label="label" value="count" unit="" max="auto" /> : <p className="text-sm text-muted-foreground">—</p>}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("an.distribution")}</CardTitle></CardHeader>
          <CardContent><PercentBars data={d.histogram} x="range" y="count" unit="" max="auto" name={t("common.count")} height={220} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("an.gender")}</CardTitle></CardHeader>
          <CardContent className="space-y-4 pt-2">
            {[["f", t("an.girls")], ["m", t("an.boys")]].map(([k, label]) => (
              <div key={k}>
                <div className="mb-1 flex justify-between text-sm"><span>{label} <span className="text-muted-foreground">({g[k]?.count ?? 0})</span></span><b className="tabular">{fmt(g[k]?.avg_percent)}%</b></div>
                <div className="h-2.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${g[k]?.avg_percent ?? 0}%` }} /></div>
              </div>
            ))}
            <div className="grid grid-cols-2 gap-2 pt-2 text-sm">
              {Object.entries(s.levels ?? {}).map(([lv, n]) => <div key={lv} className="flex justify-between rounded-md border px-2 py-1"><span>{t(`level.${lv}` as MessageKey)}</span><b className="tabular">{n as number}</b></div>)}
            </div>
          </CardContent>
        </Card>
      </div>

      {dyn && dyn.length > 1 ? (
        <Card>
          <CardHeader><CardTitle>{t("an.dynamics")} · {d.assessment.class_name}</CardTitle></CardHeader>
          <CardContent><TrendLine data={dyn.map((x) => ({ ...x, label: x.date ?? x.title }))} x="label" y="avg_percent" labelFmt={(_l, p) => p.title} /></CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader><CardTitle>{t("an.heatmap")}</CardTitle></CardHeader>
        <CardContent><Heatmap heat={d.heatmap} /></CardContent>
      </Card>
    </div>
  );
}

export default function AnalyticsPage() {
  return <Suspense><Inner /></Suspense>;
}
