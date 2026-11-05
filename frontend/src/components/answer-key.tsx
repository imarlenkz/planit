"use client";
import { BookmarkPlus, GripVertical, Library, Plus, Save, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { cn, fmt } from "@/lib/utils";

const TYPES = ["single_choice", "multiple_choice", "numeric", "short_text", "open", "essay", "math", "formula", "matching", "table", "graph", "drawing", "handwritten"];
const LETTERS = ["A", "B", "C", "D", "E"];

type Desc = { number: number; text: string; points: number; keywords?: string[] | null };
export type Q = { id?: number; number: number; text: string; answer_type: string; correct_answer: any; max_score: number; criteria?: string | null; tolerance?: number | null; options?: any; objective_id?: number | null; descriptors: Desc[] };

function toText(q: Q): string {
  const ca = q.correct_answer;
  if (ca == null) return "";
  if (q.answer_type === "numeric") return String(typeof ca === "object" && "value" in ca ? ca.value : ca);
  if (q.answer_type === "short_text") return Array.isArray(ca?.accept) ? ca.accept.join(", ") : String(ca);
  if (q.answer_type === "matching") return typeof ca === "object" ? Object.entries(ca).map(([k, v]) => `${k}-${v}`).join(", ") : String(ca);
  if (q.answer_type === "table") return typeof ca === "object" ? Object.entries(ca.cells ?? ca).map(([k, v]) => `${k}=${v}`).join("; ") : String(ca);
  return typeof ca === "string" ? ca : JSON.stringify(ca);
}

function fromText(type: string, s: string): any {
  if (type === "numeric") {
    const m = s.match(/^\s*(-?\d+(?:[.,]\d+)?)\s*\/\s*(\d+)\s*$/);
    const v = m ? Number(m[1].replace(",", ".")) / Number(m[2]) : Number(s.replace(",", "."));
    return { value: Number.isFinite(v) ? v : s };
  }
  if (type === "short_text") return { accept: s.split(",").map((x) => x.trim()).filter(Boolean) };
  if (type === "matching") return Object.fromEntries(s.split(/[,;]/).map((p) => p.split(/[-–:=]/).map((x) => x.trim())).filter((p) => p.length === 2 && p[0]));
  if (type === "table") return { cells: Object.fromEntries(s.split(";").map((p) => p.split("=").map((x) => x.trim())).filter((p) => p.length === 2)) };
  return s;
}

export function QuestionEditor({ q, onChange, onRemove, objectives }: { q: Q; onChange: (q: Q) => void; onRemove: () => void; objectives: any[] }) {
  const { t } = useI18n();
  const [answerText, setAnswerText] = useState(toText(q));
  const choice = q.answer_type === "single_choice" || q.answer_type === "multiple_choice";
  const opts: Record<string, string> = (q.options && !Array.isArray(q.options) ? q.options : null) ?? { A: "", B: "", C: "", D: "" };
  const descSum = q.descriptors.reduce((s, d) => s + Number(d.points || 0), 0);
  const set = (patch: Partial<Q>) => onChange({ ...q, ...patch });
  const selected: string[] = Array.isArray(q.correct_answer) ? q.correct_answer : q.correct_answer ? [String(q.correct_answer)] : [];

  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <div className="mt-1 flex flex-col items-center gap-1 text-muted-foreground">
          <GripVertical className="size-4" />
          <span className="grid size-8 place-items-center rounded-md bg-primary/10 text-sm font-semibold text-primary">{q.number}</span>
        </div>
        <div className="grid flex-1 gap-3">
          <div className="grid gap-3 md:grid-cols-[1fr_220px_110px]">
            <Field label={t("key.text")}>
              <Textarea rows={2} value={q.text} onChange={(e) => set({ text: e.target.value })} />
            </Field>
            <Field label={t("key.answerType")}>
              <Select
                value={q.answer_type}
                onChange={(e) => {
                  const type = e.target.value;
                  set({ answer_type: type, correct_answer: type.endsWith("choice") ? (type === "multiple_choice" ? [] : "A") : fromText(type, answerText), options: type.endsWith("choice") ? opts : null });
                }}
              >
                {TYPES.map((x) => <option key={x} value={x}>{t(`atype.${x}` as MessageKey)}</option>)}
              </Select>
            </Field>
            <Field label={t("common.max")}>
              <Input type="number" min={0.5} step={0.5} value={q.max_score} onChange={(e) => set({ max_score: Number(e.target.value) })} />
            </Field>
          </div>

          {choice ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.keys(opts).map((L) => {
                const on = selected.includes(L);
                return (
                  <div key={L} className={cn("flex items-center gap-2 rounded-md border p-1.5", on && "border-success bg-success/5")}>
                    <button
                      type="button"
                      aria-pressed={on}
                      onClick={() => {
                        if (q.answer_type === "single_choice") set({ correct_answer: L });
                        else set({ correct_answer: on ? selected.filter((x) => x !== L) : [...selected, L].sort() });
                      }}
                      className={cn("grid size-7 shrink-0 place-items-center rounded-full border text-xs font-semibold", on ? "border-success bg-success text-white" : "hover:bg-muted")}
                    >
                      {L}
                    </button>
                    <Input className="h-8 border-0 shadow-none" placeholder={`${L} ${t("key.options").toLowerCase()}`} value={opts[L] ?? ""} onChange={(e) => set({ options: { ...opts, [L]: e.target.value } })} />
                  </div>
                );
              })}
              {Object.keys(opts).length < 5 ? (
                <Button type="button" variant="ghost" size="sm" className="justify-start" onClick={() => set({ options: { ...opts, [LETTERS[Object.keys(opts).length]]: "" } })}>
                  <Plus /> {t("key.options")}
                </Button>
              ) : null}
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-[1fr_200px]">
              <Field label={t("key.correct")} hint={q.answer_type === "matching" ? "1-B, 2-C, 3-A" : q.answer_type === "table" ? "A1=5; B1=7" : q.answer_type === "short_text" ? "жауап1, жауап2" : undefined}>
                <Textarea rows={q.answer_type === "numeric" ? 1 : 2} value={answerText} onChange={(e) => { setAnswerText(e.target.value); set({ correct_answer: fromText(q.answer_type, e.target.value) }); }} />
              </Field>
              {q.answer_type === "numeric" || q.answer_type === "table" ? (
                <Field label={t("key.tolerance")}>
                  <Input type="number" step="any" min={0} value={q.tolerance ?? ""} onChange={(e) => set({ tolerance: e.target.value === "" ? null : Number(e.target.value) })} />
                </Field>
              ) : (
                <Field label={t("key.criteria")}>
                  <Textarea rows={2} value={q.criteria ?? ""} onChange={(e) => set({ criteria: e.target.value })} />
                </Field>
              )}
            </div>
          )}

          <Field label={t("key.objective")}>
            <Select value={q.objective_id ?? ""} onChange={(e) => set({ objective_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">—</option>
              {objectives.map((o) => <option key={o.id} value={o.id}>{o.code} — {o.description}</option>)}
            </Select>
          </Field>

          <div className="space-y-2 rounded-md bg-muted/40 p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">{t("key.descriptors")}</p>
              <span className={cn("text-xs tabular", descSum > q.max_score ? "font-semibold text-destructive" : "text-muted-foreground")}>
                Σ {fmt(descSum)} / {fmt(q.max_score)}
              </span>
            </div>
            {q.descriptors.map((d, i) => (
              <div key={i} className="grid grid-cols-[28px_1fr_70px_32px] items-start gap-2 md:grid-cols-[28px_1fr_1fr_70px_32px]">
                <span className="pt-2 text-center text-xs font-semibold text-muted-foreground">{d.number}</span>
                <Input value={d.text} placeholder="Дескриптор" onChange={(e) => set({ descriptors: q.descriptors.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)) })} />
                <Input className="hidden md:block" value={(d.keywords ?? []).join(", ")} placeholder={t("key.keywords")} onChange={(e) => set({ descriptors: q.descriptors.map((x, j) => (j === i ? { ...x, keywords: e.target.value.split(",").map((k) => k.trim()).filter(Boolean) } : x)) })} />
                <Input type="number" min={0.5} step={0.5} value={d.points} onChange={(e) => set({ descriptors: q.descriptors.map((x, j) => (j === i ? { ...x, points: Number(e.target.value) } : x)) })} aria-label={t("key.points")} />
                <Button type="button" variant="ghost" size="icon" onClick={() => set({ descriptors: q.descriptors.filter((_, j) => j !== i).map((x, j) => ({ ...x, number: j + 1 })) })} aria-label={t("common.delete")}>
                  <Trash2 />
                </Button>
              </div>
            ))}
            <Button type="button" variant="ghost" size="sm" onClick={() => set({ descriptors: [...q.descriptors, { number: q.descriptors.length + 1, text: "", points: 1, keywords: [] }] })}>
              <Plus /> {t("key.addDescriptor")}
            </Button>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <Button type="button" variant="ghost" size="icon" onClick={onRemove} aria-label={t("common.delete")}>
            <Trash2 className="text-destructive" />
          </Button>
          {q.id ? (
            <Button type="button" variant="ghost" size="icon" aria-label={t("key.toBank")} title={t("key.toBank")} onClick={() => api(`/question-bank/from-question/${q.id}`, { method: "POST" }).then(() => toast.success(t("common.saved")))}>
              <BookmarkPlus />
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function BankDialog({ assessmentId, onAdded }: { assessmentId: number; onAdded: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const { data } = useApi<any>(open ? "/question-bank?size=100" : null);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline"><Library /> {t("key.fromBank")}</Button>
      </DialogTrigger>
      <DialogContent title={t("bank.title")} wide>
        <div className="max-h-[60vh] space-y-2 overflow-y-auto">
          {data?.items.length ? data.items.map((it: any) => (
            <div key={it.id} className="flex items-center gap-3 rounded-md border p-3">
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm">{it.text}</p>
                <p className="text-xs text-muted-foreground">{t(`atype.${it.answer_type}` as MessageKey)} · {fmt(it.max_score)} {t("key.points").toLowerCase()}</p>
              </div>
              <Button size="sm" onClick={async () => { await api(`/question-bank/${it.id}/add-to/${assessmentId}`, { method: "POST" }); toast.success(t("common.saved")); onAdded(); }}>
                <Plus /> {t("common.add")}
              </Button>
            </div>
          )) : <EmptyState title={t("common.empty")} />}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function AnswerKeyEditor({ assessment, onSaved }: { assessment: any; onSaved: () => void }) {
  const { t } = useI18n();
  const [qs, setQs] = useState<Q[]>(assessment.questions);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: objectives } = useApi<any[]>(`/objectives?subject_id=${assessment.subject_id}`);
  useEffect(() => setQs(assessment.questions), [assessment]);
  const total = qs.reduce((s, q) => s + Number(q.max_score || 0), 0);

  async function save() {
    for (const q of qs) {
      if (q.descriptors.reduce((s, d) => s + Number(d.points), 0) > q.max_score + 1e-9) {
        toast.error(`${q.number}: ${t("key.sumMismatch")}`);
        return;
      }
    }
    setBusy(true);
    try {
      await api(`/assessments/${assessment.id}/questions`, {
        method: "PUT",
        json: qs.map(({ id: _id, ...q }) => ({ ...q, descriptors: q.descriptors.filter((d) => d.text.trim()) })),
      });
      toast.success(t("common.saved"));
      onSaved();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function importFile(f: File) {
    const fd = new FormData();
    fd.append("file", f);
    try {
      await api(`/assessments/${assessment.id}/questions/import`, { method: "POST", body: fd });
      toast.success(t("common.saved"));
      onSaved();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-sm text-muted-foreground">
          {t("assess.questions")}: <b className="text-foreground">{qs.length}</b> · {t("assess.maxScore")}: <b className="text-foreground tabular">{fmt(total)}</b>
        </p>
        <input ref={fileRef} type="file" accept=".json,.xlsx" className="hidden" onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} />
        <Button variant="outline" onClick={() => fileRef.current?.click()}><Upload /> {t("key.import")}</Button>
        <BankDialog assessmentId={assessment.id} onAdded={onSaved} />
        <Button onClick={save} loading={busy}><Save /> {t("key.save")}</Button>
      </div>
      {qs.length === 0 ? <EmptyState title={t("key.empty")} /> : null}
      {qs.map((q, i) => (
        <QuestionEditor key={`${q.id ?? "n"}-${i}`} q={q} objectives={objectives ?? []} onChange={(nq) => setQs(qs.map((x, j) => (j === i ? nq : x)))} onRemove={() => setQs(qs.filter((_, j) => j !== i).map((x, j) => ({ ...x, number: j + 1 })))} />
      ))}
      <Button variant="outline" className="w-full border-dashed" onClick={() => setQs([...qs, { number: qs.length + 1, text: "", answer_type: "single_choice", correct_answer: "A", max_score: 1, options: { A: "", B: "", C: "", D: "" }, descriptors: [] }])}>
        <Plus /> {t("key.addQuestion")}
      </Button>
    </div>
  );
}
