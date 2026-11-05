"use client";
import { BarChart3, ClipboardCheck, FileSpreadsheet, KeyRound, ScanLine, Trash2, Trophy, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";
import { AnswerKeyEditor } from "@/components/answer-key";
import { TypeBadge } from "@/components/common";
import { ResultsTable } from "@/components/results-table";
import { ScanUpload } from "@/components/scan-upload";
import { BatchActions, SubmissionsTable } from "@/components/submissions-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { fmt } from "@/lib/utils";

function AssessmentDetail() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const { t } = useI18n();
  const { data: a, error, loading, reload } = useApi<any>(`/assessments/${id}`);
  const [tab, setTab] = useState(params.get("tab") ?? "scan");
  const [rk, setRk] = useState(0);
  const [confirmDel, setConfirmDel] = useState(false);
  const refresh = () => { reload(); setRk((x) => x + 1); };
  if (error) return <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} />;
  if (loading && !a) return <Skeleton className="h-96" />;
  if (!a) return null;
  return (
    <div>
      <PageHeader
        title={a.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <TypeBadge type={a.type} /> {a.class_name} · {a.subject_name} · {a.date ?? ""} · {t("assess.maxScore")}: <b className="tabular">{fmt(a.max_score)}</b>
            <Badge variant={a.status === "completed" ? "success" : "secondary"}>{t(`assess.status.${a.status}` as MessageKey)}</Badge>
          </span>
        }
        actions={
          <>
            <Button variant="outline" asChild><Link href={`/analytics?assessment=${a.id}`}><BarChart3 /> {t("nav.analytics")}</Link></Button>
            <Button variant="outline" asChild><Link href={`/reports?assessment=${a.id}`}><FileSpreadsheet /> {t("nav.reports")}</Link></Button>
            <Dialog open={confirmDel} onOpenChange={setConfirmDel}>
              <DialogTrigger asChild><Button variant="ghost" size="icon" aria-label={t("common.delete")}><Trash2 className="text-destructive" /></Button></DialogTrigger>
              <DialogContent title={t("common.delete")} description={a.title}>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setConfirmDel(false)}>{t("common.cancel")}</Button>
                  <Button variant="destructive" onClick={async () => { await api(`/assessments/${a.id}`, { method: "DELETE" }); toast.success(t("common.saved")); router.push("/dashboard"); }}>{t("common.delete")}</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        }
      />
      <Tabs value={tab} onValueChange={(v) => { setTab(v); refresh(); }}>
        <TabsList>
          <TabsTrigger value="key"><KeyRound /> {t("assess.key")} <span className="text-xs text-muted-foreground">({a.questions.length})</span></TabsTrigger>
          <TabsTrigger value="scan"><ScanLine /> {t("assess.upload")}</TabsTrigger>
          <TabsTrigger value="works"><Users /> {t("assess.submissions")} <span className="text-xs text-muted-foreground">({a.submission_count})</span>{a.needs_review ? <Badge variant="warning">{a.needs_review}</Badge> : null}</TabsTrigger>
          <TabsTrigger value="results"><Trophy /> {t("assess.results")}</TabsTrigger>
        </TabsList>
        <TabsContent value="key"><AnswerKeyEditor assessment={a} onSaved={refresh} /></TabsContent>
        <TabsContent value="scan"><ScanUpload assessment={a} onDone={refresh} /></TabsContent>
        <TabsContent value="works" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button variant="outline" asChild><Link href={`/review?assessment=${a.id}`}><ClipboardCheck /> {t("review.title")}</Link></Button>
            <BatchActions assessmentId={a.id} onDone={refresh} />
          </div>
          <SubmissionsTable assessmentId={a.id} refreshKey={rk} />
        </TabsContent>
        <TabsContent value="results"><ResultsTable assessmentId={a.id} refreshKey={rk} /></TabsContent>
      </Tabs>
    </div>
  );
}

export default function Page() {
  return <Suspense><AssessmentDetail /></Suspense>;
}
