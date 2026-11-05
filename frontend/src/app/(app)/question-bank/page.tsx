"use client";
import { Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { QuestionEditor, type Q } from "@/components/answer-key";
import { NewAssessmentDialog } from "@/components/new-assessment";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Pagination } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useApi, useDebounced } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { fmt } from "@/lib/utils";

function ItemDialog({ item, subjects, onClose, onSaved }: { item: any; subjects: any[]; onClose: () => void; onSaved: () => void }) {
  const { t } = useI18n();
  const [meta, setMeta] = useState<any>({ subject_id: item.subject_id ?? subjects[0]?.id, grade: item.grade ?? 5, topic: item.topic ?? "", section: item.section ?? "", tags: (item.tags ?? []).join(", ") });
  const [q, setQ] = useState<Q>({ number: 1, text: item.text ?? "", answer_type: item.answer_type ?? "single_choice", correct_answer: item.correct_answer ?? null, max_score: item.max_score ?? 1, criteria: item.criteria, tolerance: item.tolerance, options: item.options, objective_id: item.objective_id, descriptors: item.descriptors ?? [] });
  const { data: objectives } = useApi<any[]>(`/objectives?subject_id=${meta.subject_id ?? ""}`, [meta.subject_id]);
  const save = async () => {
    const json = { ...meta, grade: Number(meta.grade) || null, tags: meta.tags.split(",").map((s: string) => s.trim()).filter(Boolean), text: q.text, answer_type: q.answer_type, correct_answer: q.correct_answer, max_score: q.max_score, criteria: q.criteria ?? null, tolerance: q.tolerance ?? null, options: q.options ?? null, objective_id: q.objective_id ?? null, descriptors: q.descriptors };
    try {
      if (item.id) await api(`/question-bank/${item.id}`, { method: "PUT", json });
      else await api("/question-bank", { method: "POST", json });
      toast.success(t("common.saved"));
      onSaved();
      onClose();
    } catch (e: any) { toast.error(e.message); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent wide title={item.id ? t("common.edit") : t("bank.newItem")}>
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label={t("common.subject")}>
            <Select value={meta.subject_id ?? ""} onChange={(e) => setMeta({ ...meta, subject_id: Number(e.target.value) })}>
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </Field>
          <Field label={t("cls.grade")}><Input type="number" min={1} max={12} value={meta.grade} onChange={(e) => setMeta({ ...meta, grade: e.target.value })} /></Field>
          <Field label={t("assess.topic")}><Input value={meta.topic} onChange={(e) => setMeta({ ...meta, topic: e.target.value })} /></Field>
          <Field label="Tags"><Input value={meta.tags} onChange={(e) => setMeta({ ...meta, tags: e.target.value })} /></Field>
        </div>
        <div className="max-h-[60vh] overflow-y-auto rounded-lg border scrollbar-thin">
          <QuestionEditor q={q} onChange={setQ} onRemove={onClose} objectives={objectives ?? []} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
          <Button onClick={save} disabled={!q.text}>{t("common.save")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Generator({ subjects }: { subjects: any[] }) {
  const { t } = useI18n();
  const [prompt, setPrompt] = useState("");
  const [count, setCount] = useState(6);
  const [subjectId, setSubjectId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<any | null>(null);
  const run = async () => {
    setBusy(true);
    try {
      setDraft(await api("/ai/generate-assessment", { method: "POST", json: { prompt, question_count: count, subject_id: Number(subjectId) || null } }));
    } catch (e: any) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Sparkles className="size-5 text-primary" /> {t("bank.generate")}</CardTitle>
        <CardDescription>{t("bank.prompt")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea rows={2} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={t("bank.prompt")} />
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("common.subject")}>
            <Select className="w-48" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
              <option value="">—</option>
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </Field>
          <Field label={t("bank.count")}><Input className="w-24" type="number" min={1} max={30} value={count} onChange={(e) => setCount(Number(e.target.value))} /></Field>
          <Button onClick={run} loading={busy} disabled={prompt.trim().length < 5}><Sparkles /> {t("bank.generate")}</Button>
        </div>
        {draft ? (
          <div className="space-y-3 rounded-lg border bg-muted/30 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <b className="mr-auto">{t("bank.generated")}: {draft.title}</b>
              <Badge variant="secondary">{t("bank.source")}: {draft.source}</Badge>
              <Badge>{t("assess.maxScore")}: {fmt(draft.max_score)}</Badge>
            </div>
            {draft.note ? <p className="text-xs text-muted-foreground">{draft.note}</p> : null}
            <ol className="space-y-2 text-sm">
              {draft.questions.map((q: any, i: number) => (
                <li key={i} className="rounded-md border bg-card p-2">
                  <div className="flex gap-2"><b>{q.number ?? i + 1}.</b><span className="flex-1">{q.text}</span><span className="text-xs text-muted-foreground">{t(`atype.${q.answer_type}` as MessageKey)} · {fmt(q.max_score)}</span></div>
                  {q.descriptors?.length ? <ul className="mt-1 list-inside list-disc pl-5 text-xs text-muted-foreground">{q.descriptors.map((d: any, j: number) => <li key={j}>{d.text} ({fmt(d.points)})</li>)}</ul> : null}
                </li>
              ))}
            </ol>
            <NewAssessmentDialog draft={draft} trigger={<Button><Plus /> {t("bank.createFromDraft")}</Button>} />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function QuestionBankPage() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const [editing, setEditing] = useState<any | null>(null);
  const { data: subjects } = useApi<any[]>("/subjects");
  const { data, error, loading, reload } = useApi<any>(`/question-bank?page=${page}&size=20${dq ? `&q=${encodeURIComponent(dq)}` : ""}${subjectId ? `&subject_id=${subjectId}` : ""}`);
  const subjName = (id: number) => subjects?.find((s) => s.id === id)?.name ?? "";
  const del = async (id: number) => {
    try { await api(`/question-bank/${id}`, { method: "DELETE" }); reload(); } catch (e: any) { toast.error(e.message); }
  };
  return (
    <div className="space-y-6">
      <PageHeader title={t("bank.title")} actions={<Button onClick={() => setEditing({})}><Plus /> {t("bank.newItem")}</Button>} />
      <Generator subjects={subjects ?? []} />
      <div className="flex flex-wrap gap-2">
        <Input className="w-full sm:w-72" placeholder={t("common.search")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <Select className="w-full sm:w-48" value={subjectId} onChange={(e) => { setSubjectId(e.target.value); setPage(1); }}>
          <option value="">{t("common.all")}</option>
          {subjects?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
      </div>
      {error ? <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} /> : loading && !data ? <Skeleton className="h-64" /> : !data?.items?.length ? <EmptyState title={t("bank.empty")} /> : (
        <div className="space-y-2">
          {data.items.map((it: any) => (
            <Card key={it.id}>
              <CardContent className="flex flex-wrap items-start gap-3 p-4">
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="font-medium">{it.text}</p>
                  <div className="flex flex-wrap gap-1.5 text-xs">
                    <Badge variant="secondary">{subjName(it.subject_id)}</Badge>
                    {it.grade ? <Badge variant="secondary">{it.grade}-сынып</Badge> : null}
                    <Badge variant="outline">{t(`atype.${it.answer_type}` as MessageKey)}</Badge>
                    <Badge variant="outline">{fmt(it.max_score)} {t("common.score").toLowerCase()}</Badge>
                    {it.topic ? <span className="text-muted-foreground">{it.topic}</span> : null}
                    {it.tags?.map((tag: string) => <span key={tag} className="text-muted-foreground">#{tag}</span>)}
                  </div>
                </div>
                <Button size="icon" variant="ghost" aria-label={t("common.edit")} onClick={() => setEditing(it)}><Pencil /></Button>
                <Button size="icon" variant="ghost" aria-label={t("common.delete")} onClick={() => del(it.id)}><Trash2 className="text-destructive" /></Button>
              </CardContent>
            </Card>
          ))}
          <Pagination page={page} size={20} total={data.total} onPage={setPage} labels={{ prev: t("common.prev"), next: t("common.next") }} />
        </div>
      )}
      {editing ? <ItemDialog item={editing} subjects={subjects ?? []} onClose={() => setEditing(null)} onSaved={reload} /> : null}
    </div>
  );
}
