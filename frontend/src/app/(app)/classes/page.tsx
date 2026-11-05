"use client";
import { Plus, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { UstazImport } from "@/components/ustaz-import";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";

function NewClass({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<any>({ name: "", grade: 5, academic_year: "2026-2027" });
  const { data: teachers } = useApi<any[]>(open ? "/teachers" : null, [open]);
  const save = async () => {
    try {
      await api("/classes", { method: "POST", json: { ...f, homeroom_teacher_id: f.homeroom_teacher_id || null } });
      toast.success(t("common.saved"));
      setOpen(false);
      onDone();
    } catch (e: any) { toast.error(e.message); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button><Plus /> {t("cls.new")}</Button></DialogTrigger>
      <DialogContent title={t("cls.new")}>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("common.class")}><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="9В" /></Field>
          <Field label={t("cls.grade")}><Input type="number" min={0} max={12} value={f.grade} onChange={(e) => setF({ ...f, grade: Number(e.target.value) })} /></Field>
          <Field label={t("assess.year")}><Input value={f.academic_year} onChange={(e) => setF({ ...f, academic_year: e.target.value })} /></Field>
          <Field label={t("cls.teacher")}>
            <Select value={f.homeroom_teacher_id ?? ""} onChange={(e) => setF({ ...f, homeroom_teacher_id: Number(e.target.value) || null })}>
              <option value="">—</option>
              {teachers?.map((x) => <option key={x.id} value={x.id}>{x.full_name}</option>)}
            </Select>
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} disabled={!f.name}>{t("common.create")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ClassesPage() {
  const { t } = useI18n();
  const { data, error, loading, reload } = useApi<any[]>("/classes");
  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.classes")} actions={<div className="flex flex-wrap gap-2"><UstazImport onDone={reload} /><NewClass onDone={reload} /></div>} />
      {error ? <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} /> : loading && !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32" />)}</div>
      ) : !data?.length ? <EmptyState title={t("common.empty")} /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {data.map((c) => (
            <Link key={c.id} href={`/classes/${c.id}`} className="group">
              <Card className="h-full transition-shadow group-hover:shadow-md">
                <CardHeader className="pb-2"><CardTitle className="text-2xl">{c.name}</CardTitle></CardHeader>
                <CardContent className="flex items-center justify-between text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5"><Users className="size-4" /> {c.student_count} {t("cls.students")}</span>
                  <span>{c.academic_year}</span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
