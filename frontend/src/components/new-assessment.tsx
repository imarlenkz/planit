"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { TYPE_LABEL, cn } from "@/lib/utils";

export function NewAssessmentDialog({ trigger, defaultType = "BZhB", draft }: { trigger: React.ReactNode; defaultType?: string; draft?: any }) {
  const { t } = useI18n();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { data: classes } = useApi<any[]>(open ? "/classes" : null);
  const { data: subjects } = useApi<any[]>(open ? "/subjects" : null);
  const [f, setF] = useState<any>({ type: defaultType, academic_year: "2026-2027", quarter: 2, date: new Date().toISOString().slice(0, 10), title: draft?.title ?? "", section: draft?.section ?? "" });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const subject = subjects?.find((s) => s.id === Number(f.subject_id));
      const cls = classes?.find((c) => c.id === Number(f.class_id));
      const title = f.title || `${subject?.name ?? ""} ${TYPE_LABEL[f.type]} — ${f.section || cls?.name || ""}`.trim();
      const a = await api("/assessments", {
        method: "POST",
        json: { ...f, title, subject_id: Number(f.subject_id), class_id: Number(f.class_id), quarter: f.quarter ? Number(f.quarter) : null, max_score: Number(f.max_score || 0), date: f.date || null },
      });
      if (draft?.questions?.length) {
        await api(`/assessments/${a.id}/questions`, { method: "PUT", json: draft.questions.map((q: any) => ({ ...q, options: q.options ?? null, correct_answer: q.correct_answer ?? null })) });
      }
      toast.success(t("common.saved"));
      setOpen(false);
      router.push(`/assessment/${a.id}?tab=key`);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent title={t("assess.new")} wide>
        <form onSubmit={submit} className="grid gap-4">
          <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label={t("assess.type")}>
            {["BZhB", "TZhB", "AB"].map((ty) => (
              <button
                key={ty}
                type="button"
                role="radio"
                aria-checked={f.type === ty}
                onClick={() => set("type", ty)}
                className={cn("rounded-lg border p-3 text-center transition-colors", f.type === ty ? "border-primary bg-primary/5 ring-1 ring-primary" : "hover:bg-muted")}
              >
                <span className="block text-lg font-semibold">{TYPE_LABEL[ty]}</span>
                <span className="text-xs text-muted-foreground">{t(ty === "BZhB" ? "nav.bzhb" : ty === "TZhB" ? "nav.tzhb" : "nav.ab")}</span>
              </button>
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("common.subject")}>
              <Select required value={f.subject_id ?? ""} onChange={(e) => set("subject_id", e.target.value)}>
                <option value="" disabled>{t("common.select")}</option>
                {subjects?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label={t("common.class")}>
              <Select required value={f.class_id ?? ""} onChange={(e) => set("class_id", e.target.value)}>
                <option value="" disabled>{t("common.select")}</option>
                {classes?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label={t("assess.year")}>
              <Input value={f.academic_year} onChange={(e) => set("academic_year", e.target.value)} pattern="\d{4}-\d{4}" />
            </Field>
            <Field label={t("assess.quarter")}>
              <Select value={f.quarter} onChange={(e) => set("quarter", e.target.value)}>
                {[1, 2, 3, 4].map((q) => <option key={q} value={q}>{q}</option>)}
              </Select>
            </Field>
            <Field label={t("assess.section")}>
              <Input value={f.section ?? ""} onChange={(e) => set("section", e.target.value)} placeholder="Жай бөлшектер" />
            </Field>
            <Field label={t("assess.topic")}>
              <Input value={f.topic ?? ""} onChange={(e) => set("topic", e.target.value)} />
            </Field>
            <Field label={t("assess.date")}>
              <Input type="date" value={f.date} onChange={(e) => set("date", e.target.value)} />
            </Field>
            <Field label={t("assess.maxScore")}>
              <Input type="number" min={0} value={f.max_score ?? ""} onChange={(e) => set("max_score", e.target.value)} placeholder="20" />
            </Field>
            <Field label={t("assess.title")} className="sm:col-span-2">
              <Input value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="Математика БЖБ №2 — Жай бөлшектер" />
            </Field>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button type="submit" loading={busy}>{t("common.create")}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
