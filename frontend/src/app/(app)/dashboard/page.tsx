"use client";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, FileCheck2, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { NewAssessmentDialog } from "@/components/new-assessment";
import { TypeBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, PageHeader, Skeleton, Stat } from "@/components/ui/misc";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { fmt, pctColor } from "@/lib/utils";

const SPLIT_COLORS: Record<string, string> = { auto_approved: "#16a34a", approved: "#0f766e", medium: "#3b82f6", needs_review: "#f59e0b", overridden: "#8b5cf6" };

export default function Dashboard() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<any>("/analytics/dashboard");
  if (error) return <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} />;
  const c = data?.cards;
  const split = data ? Object.entries(data.review_split as Record<string, number>).map(([k, v]) => ({ name: t(`rstatus.${k}` as MessageKey), key: k, value: v })) : [];
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("dash.title")}
        description={`${t("auth.welcome")}, ${user?.full_name}`}
        actions={<NewAssessmentDialog trigger={<Button><Plus /> {t("dash.newAssessment")}</Button>} />}
      />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {loading || !c ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)
        ) : (
          <>
            <Stat label={t("dash.checkedToday")} value={c.checked_today} icon={FileCheck2} tone="primary" />
            <Stat label={t("dash.inProgress")} value={c.in_progress} icon={Clock3} tone="primary" />
            <Link href="/review" className="block transition-transform hover:-translate-y-0.5">
              <Stat label={t("dash.needsReview")} value={c.needs_review} icon={AlertTriangle} tone="warning" hint={c.unknown_students ? `${t("sub.unknown")}: ${c.unknown_students}` : undefined} />
            </Link>
            <Stat label={t("dash.completed")} value={c.completed} icon={CheckCircle2} tone="success" hint={`${t("common.total")}: ${c.total_submissions}`} />
          </>
        )}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{t("dash.recent")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {loading ? (
              <Skeleton className="h-40" />
            ) : (
              data?.recent.map((a: any) => (
                <Link key={a.id} href={`/assessment/${a.id}`} className="flex items-center gap-3 rounded-md px-2 py-2.5 hover:bg-muted/60">
                  <TypeBadge type={a.type} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{a.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {a.class_name} · {a.subject} · {a.date ?? ""}
                    </p>
                  </div>
                  <span className={`text-sm font-semibold tabular ${pctColor(a.avg_percent)}`}>{a.avg_percent != null ? `${fmt(a.avg_percent)}%` : "—"}</span>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </Link>
              ))
            )}
          </CardContent>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" /> {t("dash.quickFlow")}</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-2.5 text-sm">
                {(["dash.flow1", "dash.flow2", "dash.flow3", "dash.flow4", "dash.flow5"] as const).map((k, i) => (
                  <li key={k} className="flex items-center gap-3">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{i + 1}</span>
                    {t(k)}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("dash.reviewSplit")}</CardTitle>
            </CardHeader>
            <CardContent>
              {split.length ? (
                <div className="flex items-center gap-4">
                  <div className="h-32 w-32">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={split} dataKey="value" innerRadius={34} outerRadius={60} paddingAngle={2} stroke="none">
                          {split.map((s) => <Cell key={s.key} fill={SPLIT_COLORS[s.key] ?? "#94a3b8"} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <ul className="space-y-1 text-xs">
                    {split.map((s) => (
                      <li key={s.key} className="flex items-center gap-2">
                        <span className="size-2.5 rounded-full" style={{ background: SPLIT_COLORS[s.key] }} />
                        {s.name}: <b className="tabular">{s.value}</b>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
