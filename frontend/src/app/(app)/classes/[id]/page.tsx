"use client";
import { ArrowLeft, ListPlus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { TrendLine } from "@/components/charts";
import { TypeBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";

function BulkAdd({ classId, onDone }: { classId: number; onDone: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const save = async () => {
    const names = text.split("\n").map((s) => s.trim()).filter(Boolean);
    try {
      const r = await api<any>(`/students/bulk?class_id=${classId}`, { method: "POST", json: names });
      toast.success(t("cls.added", { n: r.created ?? names.length }));
      setOpen(false);
      setText("");
      onDone();
    } catch (e: any) { toast.error(e.message); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button variant="outline"><ListPlus /> {t("cls.bulk")}</Button></DialogTrigger>
      <DialogContent title={t("cls.bulk")} description="Аты Тегі;m / Аты Тегі;f">
        <Field label={t("cls.roster")}><Textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder={"Әлихан Бекұлы;m\nАйару Нұрланқызы;f"} /></Field>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} disabled={!text.trim()}>{t("common.add")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ClassDetail() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const { data: classes } = useApi<any[]>("/classes");
  const c = classes?.find((x) => String(x.id) === id);
  const { data: students, reload } = useApi<any>(`/students?class_id=${id}&size=200`);
  const { data: dyn } = useApi<any[]>(`/analytics/classes/${id}/dynamics`);
  const { data: assessments } = useApi<any>(`/assessments?class_id=${id}&size=100`);
  return (
    <div className="space-y-6">
      <PageHeader
        title={c ? `${c.name} ${t("common.class").toLowerCase()}` : "…"}
        description={c ? `${c.student_count} ${t("cls.students")} · ${c.academic_year}` : undefined}
        actions={<><Button variant="ghost" asChild><Link href="/classes"><ArrowLeft /> {t("common.back")}</Link></Button><BulkAdd classId={Number(id)} onDone={reload} /></>}
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <Card>
          <CardHeader><CardTitle>{t("an.dynamics")}</CardTitle></CardHeader>
          <CardContent>
            {!dyn ? <Skeleton className="h-60" /> : dyn.length ? <TrendLine data={dyn.map((x) => ({ ...x, label: x.date ?? x.title }))} x="label" y="avg_percent" labelFmt={(_l, p) => `${p.subject} · ${p.title}`} /> : <EmptyState title={t("common.empty")} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("cls.assessments")}</CardTitle></CardHeader>
          <CardContent className="space-y-1 p-2">
            {assessments?.items?.length ? assessments.items.map((a: any) => (
              <Link key={a.id} href={`/assessment/${a.id}`} className="flex items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-muted">
                <TypeBadge type={a.type} /><span className="min-w-0 flex-1 truncate">{a.title}</span>
                <span className="text-xs text-muted-foreground">{a.date}</span>
              </Link>
            )) : <p className="p-2 text-sm text-muted-foreground">{t("common.empty")}</p>}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>{t("cls.roster")}</CardTitle></CardHeader>
        <CardContent className="p-0">
          <Table>
            <THead><TR><TH>#</TH><TH>{t("stu.name")}</TH><TH>{t("stu.gender")}</TH><TH>{t("stu.code")}</TH><TH /></TR></THead>
            <TBody>
              {students?.items?.map((s: any, i: number) => (
                <TR key={s.id}>
                  <TD className="tabular text-muted-foreground">{i + 1}</TD>
                  <TD className="font-medium">{s.full_name}</TD>
                  <TD>{s.gender === "f" ? t("stu.female") : s.gender === "m" ? t("stu.male") : "—"}</TD>
                  <TD className="font-mono text-xs">{s.student_code}</TD>
                  <TD className="text-right"><Button size="sm" variant="ghost" asChild><Link href={`/students?student=${s.id}`}>{t("stu.history")}</Link></Button></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
