"use client";
import { ArrowLeft, CheckCheck, ChevronLeft, ChevronRight, UserRoundSearch } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { SubmissionBadge } from "@/components/common";
import { AnswerRow, EvalPanel } from "@/components/eval-panel";
import { ResultSummary } from "@/components/result-view";
import { ScanViewer, type Region } from "@/components/scan-viewer";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { ErrorState, Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { fmt, pctColor } from "@/lib/utils";

export default function SubmissionReview() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t } = useI18n();
  const { user } = useAuth();
  const staff = isStaff(user);
  const { data: sub, error, loading, reload } = useApi<any>(`/submissions/${id}`);
  const { data: siblings } = useApi<any[]>(staff && sub ? `/assessments/${sub.assessment_id}/submissions` : null, [sub?.assessment_id]);
  const { data: roster } = useApi<any[]>(staff && sub && !sub.student_id ? `/assessments/${sub.assessment_id}/students` : null, [sub?.student_id]);
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (sub && (selected === null || !sub.answers.some((a: any) => a.id === selected))) {
      const q = typeof window !== "undefined" ? Number(new URLSearchParams(window.location.search).get("q")) : 0;
      const first = (q ? sub.answers.find((a: any) => a.number === q) : null) ?? sub.answers.find((a: any) => a.evaluation?.review_status === "needs_review") ?? sub.answers[0];
      setSelected(first?.id ?? null);
    }
  }, [sub]);

  const regions: Region[] = useMemo(
    () => (sub?.answers ?? []).map((a: any) => ({
      id: a.id, number: a.number, page_id: a.page_id, bbox: a.bbox,
      tone: !a.evaluation ? "primary" : a.evaluation.review_status === "needs_review" ? "warning" : a.evaluation.status === "correct" ? "success" : a.evaluation.status === "incorrect" ? "destructive" : "primary",
    })),
    [sub],
  );

  if (error) return <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} />;
  if (loading && !sub) return <Skeleton className="h-[80vh]" />;
  if (!sub) return null;

  const idx = siblings?.findIndex((s) => s.id === sub.id) ?? -1;
  const prev = idx > 0 ? siblings![idx - 1] : null;
  const next = siblings && idx >= 0 && idx < siblings.length - 1 ? siblings[idx + 1] : null;
  const current = sub.answers.find((a: any) => a.id === selected);
  const pending = sub.answers.filter((a: any) => a.evaluation?.review_status === "needs_review").length;

  async function assign(studentId: number) {
    try {
      await api(`/submissions/${sub.id}/student`, { method: "PATCH", json: { student_id: studentId } });
      toast.success(t("common.saved"));
      reload();
    } catch (e: any) {
      toast.error(e.message);
    }
  }
  async function approve() {
    setBusy(true);
    try {
      await api(`/submissions/${sub.id}/approve`, { method: "POST" });
      toast.success(t("sub.status.approved"));
      if (next) router.push(`/submissions/${next.id}`);
      else reload();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!staff) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Button variant="ghost" asChild><Link href="/me"><ArrowLeft /> {t("common.back")}</Link></Button>
        <ResultSummary sub={sub} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100vh-8rem)]">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="icon" asChild aria-label={t("common.back")}><Link href={`/assessment/${sub.assessment_id}?tab=works`}><ArrowLeft /></Link></Button>
        <div className="mr-auto min-w-0">
          {sub.student_id ? (
            <h1 className="truncate text-xl font-semibold">{sub.student_name}</h1>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1 font-semibold text-warning"><UserRoundSearch className="size-5" /> {t("sub.chooseStudent")}</span>
              {sub.detected_name ? <span className="text-sm text-muted-foreground">{t("sub.detectedName")}: «{sub.detected_name}»</span> : null}
              <Select className="w-64" defaultValue="" onChange={(e) => assign(Number(e.target.value))} aria-label={t("sub.chooseStudent")}>
                <option value="" disabled>{t("common.select")}</option>
                {roster?.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
              </Select>
            </div>
          )}
          <p className="text-sm text-muted-foreground">
            <SubmissionBadge status={sub.status} /> · {t("result.total")}: <b className={`tabular ${pctColor(sub.percent)}`}>{fmt(sub.total_score)}/{fmt(sub.max_score)} ({fmt(sub.percent)}%)</b>
            {pending ? <> · <span className="font-medium text-warning">{t("review.queue", { n: pending })}</span></> : null}
          </p>
        </div>
        <Button variant="outline" size="icon" disabled={!prev} onClick={() => prev && router.push(`/submissions/${prev.id}`)} aria-label={t("review.prevWork")}><ChevronLeft /></Button>
        <span className="text-sm tabular text-muted-foreground">{idx + 1}/{siblings?.length ?? "…"}</span>
        <Button variant="outline" size="icon" disabled={!next} onClick={() => next && router.push(`/submissions/${next.id}`)} aria-label={t("review.nextWork")}><ChevronRight /></Button>
        <Button variant="success" onClick={approve} loading={busy} disabled={!sub.student_id || sub.status === "approved"}><CheckCheck /> {t("review.approveWork")}</Button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(380px,1fr)]">
        <div className="h-[60vh] min-h-0 lg:h-auto">
          <ScanViewer pages={sub.pages_detail} regions={regions} selected={selected} onSelect={setSelected} />
        </div>
        <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-card">
          <Tabs defaultValue="answers" className="flex min-h-0 flex-1 flex-col">
            <div className="border-b px-3 pt-3">
              <TabsList className="mb-3">
                <TabsTrigger value="answers">{t("result.byTask")}</TabsTrigger>
                <TabsTrigger value="result">{t("assess.results")}</TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="answers" className="mt-0 flex min-h-0 flex-1 flex-col lg:flex-row">
              <div className="max-h-56 shrink-0 divide-y overflow-y-auto border-b scrollbar-thin lg:max-h-none lg:w-52 lg:border-b-0 lg:border-r">
                {sub.answers.map((a: any) => <AnswerRow key={a.id} a={a} active={a.id === selected} onClick={() => setSelected(a.id)} />)}
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
                {current ? <EvalPanel answer={current} onChanged={reload} /> : null}
              </div>
            </TabsContent>
            <TabsContent value="result" className="mt-0 min-h-0 flex-1 overflow-y-auto p-4">
              <ResultSummary sub={sub} editable onSaved={reload} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
