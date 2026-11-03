"use client";
import { AlertTriangle, CheckCheck, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { LevelBadge, SubmissionBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { fmt, pctColor } from "@/lib/utils";

export function BatchActions({ assessmentId, onDone }: { assessmentId: number; onDone: () => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  async function confident() {
    setBusy("c");
    try {
      const r = await api(`/assessments/${assessmentId}/approve-confident`, { method: "POST", json: { min_confidence: 95 } });
      toast.success(t("review.approvedN", { n: r.approved }));
      onDone();
    } catch (e: any) { toast.error(e.message); } finally { setBusy(null); }
  }
  async function all() {
    setBusy("a");
    try {
      const r = await api(`/assessments/${assessmentId}/approve-all`, { method: "POST" });
      toast.success(t("review.approvedN", { n: r.approved }));
      if (r.skipped.length) toast.warning(`${t("review.queue", { n: r.skipped.length })}`);
      setOpen(false);
      onDone();
    } catch (e: any) { toast.error(e.message); } finally { setBusy(null); }
  }
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" onClick={confident} loading={busy === "c"}><ShieldCheck /> {t("review.approveConfident")}</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild><Button variant="success"><CheckCheck /> {t("review.approveAll")}</Button></DialogTrigger>
        <DialogContent title={t("review.approveAll")} description={t("dash.flow5")}>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button variant="success" onClick={all} loading={busy === "a"}>{t("common.confirm")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function SubmissionsTable({ assessmentId, refreshKey }: { assessmentId: number; refreshKey?: number }) {
  const { t } = useI18n();
  const { data, loading } = useApi<any[]>(`/assessments/${assessmentId}/submissions`, [refreshKey]);
  if (loading && !data) return <Skeleton className="h-60" />;
  if (!data?.length) return <EmptyState title={t("common.empty")} hint={t("dash.flow3")} />;
  return (
    <Table>
      <THead>
        <TR>
          <TH>{t("common.student")}</TH>
          <TH className="hidden sm:table-cell">QR / OCR</TH>
          <TH className="text-right">{t("common.score")}</TH>
          <TH className="text-right">%</TH>
          <TH className="hidden md:table-cell">{t("result.level")}</TH>
          <TH>{t("common.status")}</TH>
          <TH className="text-right">{t("rstatus.needs_review")}</TH>
        </TR>
      </THead>
      <TBody>
        {data.map((s) => (
          <TR key={s.id}>
            <TD>
              <Link href={`/submissions/${s.id}`} className="font-medium hover:text-primary">
                {s.student_name ?? (
                  <span className="inline-flex items-center gap-1 text-warning"><AlertTriangle className="size-4" /> {t("sub.chooseStudent")}{s.detected_name ? ` («${s.detected_name}»)` : ""}</span>
                )}
              </Link>
            </TD>
            <TD className="hidden text-xs text-muted-foreground sm:table-cell">{t(`sub.method.${s.detection_method ?? "unknown"}` as MessageKey)} · {s.pages} {t("scan.pages")}</TD>
            <TD className="text-right tabular">{s.total_score != null ? `${fmt(s.total_score)}/${fmt(s.max_score)}` : "—"}</TD>
            <TD className={`text-right font-semibold tabular ${pctColor(s.percent)}`}>{s.percent != null ? `${fmt(s.percent)}%` : "—"}</TD>
            <TD className="hidden md:table-cell">{s.level ? <LevelBadge level={s.level} /> : null}</TD>
            <TD><SubmissionBadge status={s.status} /></TD>
            <TD className="text-right tabular">{s.review_counts?.needs_review ? <span className="font-semibold text-warning">{s.review_counts.needs_review}</span> : <span className="text-muted-foreground">0</span>}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
