"use client";
import { AlertTriangle, Check, History, PencilLine, RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ConfidencePill, EvalStatusBadge, ReviewBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { cn, fmt } from "@/lib/utils";

export function AnswerRow({ a, active, onClick }: { a: any; active: boolean; onClick: () => void }) {
  const ev = a.evaluation;
  const tone = !ev ? "" : ev.review_status === "needs_review" ? "border-l-warning" : ev.status === "correct" ? "border-l-success" : ev.status === "incorrect" ? "border-l-destructive" : "border-l-primary";
  return (
    <button type="button" onClick={onClick} className={cn("flex w-full items-center gap-3 border-l-4 px-3 py-2 text-left transition-colors", tone, active ? "bg-primary/5" : "hover:bg-muted/50")}>
      <span className="w-8 shrink-0 text-sm font-semibold tabular">{a.number}</span>
      <span className="min-w-0 flex-1 truncate font-mono text-sm">{a.detected_answer || <span className="italic text-muted-foreground">—</span>}</span>
      {ev ? (
        <>
          {ev.review_status === "needs_review" ? <AlertTriangle className="size-4 shrink-0 text-warning" /> : null}
          <span className="w-14 shrink-0 text-right text-sm font-semibold tabular">{fmt(ev.score)}/{fmt(ev.max_score)}</span>
        </>
      ) : null}
    </button>
  );
}

export function EvalPanel({ answer, onChanged, readOnly }: { answer: any; onChanged: (patch?: any) => void; readOnly?: boolean }) {
  const { t } = useI18n();
  const ev = answer.evaluation;
  const [mode, setMode] = useState<"view" | "override" | "recheck">("view");
  const [score, setScore] = useState<number>(ev?.score ?? 0);
  const [comment, setComment] = useState("");
  const [text, setText] = useState(answer.detected_answer ?? "");
  const [items, setItems] = useState<any[]>(ev?.items ?? []);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setMode("view");
    setScore(ev?.score ?? 0);
    setComment(ev?.teacher_comment ?? "");
    setText(answer.detected_answer ?? "");
    setItems(ev?.items ?? []);
  }, [answer.id, ev?.score, ev?.review_status]);

  if (!ev) return null;
  const doubtful = ev.review_status === "needs_review";

  async function run(fn: () => Promise<any>) {
    setBusy(true);
    try {
      await fn();
      toast.success(t("common.saved"));
      setMode("view");
      onChanged();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  const toggleItem = (id: number) => {
    const next = items.map((it) => (it.id === id ? { ...it, met: !it.met } : it));
    setItems(next);
    setScore(Math.min(ev.max_score, next.reduce((s, it) => s + (it.met ? it.points ?? 0 : 0), 0)));
  };

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-lg font-semibold">{t("common.taskN", { n: answer.number })}</h3>
        <EvalStatusBadge status={ev.status} />
        <ReviewBadge status={ev.review_status} />
      </div>
      {answer.question_text ? <p className="text-sm text-muted-foreground">{answer.question_text}</p> : null}
      {doubtful ? (
        <div className="flex items-center gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm font-medium text-warning">
          <AlertTriangle className="size-4" /> {t("review.manualRequired")} · {t("review.confidence")}: {fmt(ev.confidence, 0)}%
        </div>
      ) : null}
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div className="col-span-2 rounded-md border p-3">
          <dt className="text-xs text-muted-foreground">{t("review.studentAnswer")}</dt>
          <dd className="mt-1 whitespace-pre-wrap font-mono">{answer.detected_answer || <span className="italic text-muted-foreground">—</span>}</dd>
          {answer.flags?.length ? <dd className="mt-1 text-xs text-warning">{answer.flags.join(", ")}</dd> : null}
        </div>
        <div className="col-span-2 rounded-md border bg-muted/30 p-3">
          <dt className="text-xs text-muted-foreground">{t("review.expected")}</dt>
          <dd className="mt-1 whitespace-pre-wrap font-mono">{ev.expected_answer || "—"}</dd>
        </div>
        <div className="rounded-md border p-3">
          <dt className="text-xs text-muted-foreground">{t("review.aiScore")}</dt>
          <dd className="mt-1 text-2xl font-semibold tabular">{fmt(ev.score)}<span className="text-base text-muted-foreground">/{fmt(ev.max_score)}</span></dd>
          {ev.ai_suggested_score != null && ev.ai_suggested_score !== ev.score ? <dd className="text-xs text-muted-foreground">AI: {fmt(ev.ai_suggested_score)}</dd> : null}
        </div>
        <div className="rounded-md border p-3">
          <dt className="text-xs text-muted-foreground">{t("review.confidence")}</dt>
          <dd className="mt-1.5"><ConfidencePill value={ev.confidence} /></dd>
          <dd className="mt-1 text-xs text-muted-foreground">{t("review.ocrConfidence")}: {fmt(answer.ocr_confidence, 0)}% · {ev.method}</dd>
        </div>
      </dl>
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("review.reason")}</p>
        <p className="whitespace-pre-wrap rounded-md bg-muted/40 p-3 text-sm">{ev.reasoning}</p>
      </div>
      {items.length ? (
        <div className="space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("review.descriptorsMet")}</p>
          {items.map((it) => (
            <label key={it.id} className={cn("flex items-start gap-2 rounded-md border p-2 text-sm", mode === "override" ? "cursor-pointer hover:bg-muted/50" : "")}>
              <input type="checkbox" className="mt-0.5 size-4 accent-[hsl(var(--primary))]" checked={it.met} disabled={mode !== "override"} onChange={() => toggleItem(it.id)} />
              <span className="flex-1">
                <b>{it.number}.</b> {it.text} <span className="text-xs text-muted-foreground">({fmt(it.points)})</span>
                {it.reason ? <span className="block text-xs text-muted-foreground">{it.reason}</span> : null}
              </span>
              <span className={cn("text-xs font-semibold tabular", it.met ? "text-success" : "text-muted-foreground")}>{it.met ? `+${fmt(it.points)}` : "+0"}</span>
            </label>
          ))}
        </div>
      ) : null}
      {ev.teacher_comment && mode === "view" ? <p className="rounded-md border-l-4 border-primary bg-primary/5 p-2 text-sm">{ev.teacher_comment}</p> : null}

      {!readOnly ? (
        mode === "view" ? (
          <div className="grid grid-cols-3 gap-2">
            <Button variant="success" onClick={() => run(() => api(`/evaluations/${ev.id}/accept`, { method: "POST", json: {} }))} loading={busy}><Check /> {t("review.accept")}</Button>
            <Button variant="outline" onClick={() => setMode("override")}><PencilLine /> {t("review.override")}</Button>
            <Button variant="outline" onClick={() => setMode("recheck")}><RefreshCcw /> {t("review.recheck")}</Button>
          </div>
        ) : mode === "override" ? (
          <div className="space-y-3 rounded-md border p-3">
            <Field label={`${t("common.score")} (0–${fmt(ev.max_score)})`}>
              <div className="flex items-center gap-2">
                <Input type="number" min={0} max={ev.max_score} step={0.5} value={score} onChange={(e) => setScore(Number(e.target.value))} className="w-28" />
                <div className="flex flex-wrap gap-1">
                  {Array.from({ length: Math.floor(ev.max_score) + 1 }, (_, i) => i).map((v) => (
                    <button key={v} type="button" onClick={() => setScore(v)} className={cn("size-8 rounded-md border text-sm tabular", score === v ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted")}>{v}</button>
                  ))}
                </div>
              </div>
            </Field>
            <Field label={t("review.comment")}>
              <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="балама дұрыс жауап" />
            </Field>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setMode("view")}>{t("common.cancel")}</Button>
              <Button loading={busy} onClick={() => run(() => api(`/evaluations/${ev.id}/override`, { method: "POST", json: { score, comment: comment || null, descriptor_items: items.map((it) => ({ descriptor_id: it.descriptor_id, met: it.met })) } }))}>{t("common.save")}</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3 rounded-md border p-3">
            <Field label={t("review.editText")}>
              <Textarea value={text} onChange={(e) => setText(e.target.value)} className="font-mono" />
            </Field>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setMode("view")}>{t("common.cancel")}</Button>
              <Button loading={busy} onClick={() => run(() => api(`/evaluations/${ev.id}/recheck`, { method: "POST", json: { detected_answer: text !== answer.detected_answer ? text : null } }))}><RefreshCcw /> {t("review.recheck")}</Button>
            </div>
          </div>
        )
      ) : null}

      {ev.reviews?.length ? (
        <div className="space-y-1">
          <p className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground"><History className="size-3.5" /> {t("review.history")}</p>
          {ev.reviews.map((r: any, i: number) => (
            <p key={i} className="text-xs text-muted-foreground">
              {new Date(r.created_at).toLocaleString()} · {t(`review.${r.action}` as MessageKey)} · {fmt(r.old_score)} → {fmt(r.new_score)} {r.comment && r.comment !== "batch" ? `· ${r.comment}` : ""}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
