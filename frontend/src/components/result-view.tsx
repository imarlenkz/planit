"use client";
import { CheckCircle2, MessageSquareText, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { LevelBadge } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn, fmt, pctColor } from "@/lib/utils";

export function ResultSummary({ sub, editable, onSaved }: { sub: any; editable?: boolean; onSaved?: () => void }) {
  const { t } = useI18n();
  const r = sub.result;
  const [fb, setFb] = useState<string>(r?.feedback ?? "");
  const [editing, setEditing] = useState(false);
  if (!r) return null;
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="grid gap-4 p-5 sm:grid-cols-[auto_1fr]">
          <div className="grid size-28 place-items-center rounded-full border-8 border-primary/15">
            <div className="text-center">
              <p className={cn("text-2xl font-bold tabular", pctColor(r.percent))}>{fmt(r.percent)}%</p>
              <p className="text-xs text-muted-foreground tabular">{fmt(r.total_score)}/{fmt(r.max_score)}</p>
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">{t("result.total")}</p>
            <p className="text-3xl font-semibold tabular">{fmt(r.total_score)} / {fmt(r.max_score)}</p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">{t("result.level")}:</span> <LevelBadge level={r.level} />
              <Badge variant={r.is_final ? "success" : "secondary"}>{r.is_final ? t("result.final") : t("result.provisional")}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-sm">{t("result.strengths")}</CardTitle></CardHeader>
          <CardContent className="space-y-1.5 text-sm">
            {r.strengths?.length ? r.strengths.map((s: string) => <p key={s} className="flex gap-2"><CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" /> {s}</p>) : <p className="text-muted-foreground">—</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">{t("result.weaknesses")}</CardTitle></CardHeader>
          <CardContent className="space-y-1.5 text-sm">
            {r.weaknesses?.length ? r.weaknesses.map((s: string) => <p key={s} className="flex gap-2"><TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" /> {s}</p>) : <p className="text-muted-foreground">—</p>}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm"><MessageSquareText className="size-4" /> {t("result.feedback")}</CardTitle>
          {editable && !editing ? <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>{t("common.edit")}</Button> : null}
        </CardHeader>
        <CardContent>
          {editing ? (
            <div className="space-y-2">
              <Textarea rows={7} value={fb} onChange={(e) => setFb(e.target.value)} />
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setEditing(false)}>{t("common.cancel")}</Button>
                <Button size="sm" onClick={async () => { await api(`/results/${r.id}/feedback`, { method: "PATCH", json: { feedback: fb } }); toast.success(t("common.saved")); setEditing(false); onSaved?.(); }}>{t("common.save")}</Button>
              </div>
            </div>
          ) : (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{r.feedback}</p>
          )}
        </CardContent>
      </Card>
      <Table>
        <THead><TR><TH>№</TH><TH className="text-right">{t("common.max")}</TH><TH className="text-right">{t("common.score")}</TH><TH className="text-right">%</TH></TR></THead>
        <TBody>
          {sub.answers.map((a: any) => {
            const s = a.evaluation?.score;
            const p = s != null ? (s / a.max_score) * 100 : null;
            return (
              <TR key={a.id}>
                <TD>{a.number}</TD>
                <TD className="text-right tabular">{fmt(a.max_score)}</TD>
                <TD className="text-right tabular">{s != null ? fmt(s) : "—"}</TD>
                <TD className={`text-right font-medium tabular ${pctColor(p)}`}>{p != null ? `${fmt(p, 0)}%` : "—"}</TD>
              </TR>
            );
          })}
        </TBody>
      </Table>
    </div>
  );
}
