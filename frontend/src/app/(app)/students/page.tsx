"use client";
import { Download, Pencil, Plus, Trash2, UserX } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";
import { StudentHistory } from "@/components/student-history";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Pagination, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useApi, useDebounced } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { download } from "@/lib/utils";

function StudentForm({ initial, classes, onClose, onSaved }: { initial: any; classes: any[]; onClose: () => void; onSaved: () => void }) {
  const { t } = useI18n();
  const [f, setF] = useState<any>(initial);
  const save = async () => {
    try {
      const json = { full_name: f.full_name, class_id: f.class_id || null, gender: f.gender || null, student_code: f.student_code || null };
      if (f.id) await api(`/students/${f.id}`, { method: "PATCH", json });
      else await api("/students", { method: "POST", json });
      toast.success(t("common.saved"));
      onSaved();
      onClose();
    } catch (e: any) { toast.error(e.message); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={f.id ? t("common.edit") : t("stu.new")}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("stu.name")} className="sm:col-span-2"><Input value={f.full_name ?? ""} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label={t("common.class")}>
            <Select value={f.class_id ?? ""} onChange={(e) => setF({ ...f, class_id: Number(e.target.value) || null })}>
              <option value="">—</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
          <Field label={t("stu.gender")}>
            <Select value={f.gender ?? ""} onChange={(e) => setF({ ...f, gender: e.target.value || null })}>
              <option value="">—</option><option value="f">{t("stu.female")}</option><option value="m">{t("stu.male")}</option>
            </Select>
          </Field>
          <Field label={t("stu.code")}><Input value={f.student_code ?? ""} onChange={(e) => setF({ ...f, student_code: e.target.value })} /></Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
          <Button onClick={save} disabled={!f.full_name || f.full_name.length < 2}>{t("common.save")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function HistoryDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const { t } = useI18n();
  const { data } = useApi<any>(`/students/${id}/results`);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent wide title={data?.student?.full_name ?? "…"} description={`${data?.student?.class_name ?? ""} · ${t("stu.history")}`}>
        {data ? <StudentHistory rows={data.results} /> : <Skeleton className="h-48" />}
      </DialogContent>
    </Dialog>
  );
}

function Inner() {
  const { t } = useI18n();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [classId, setClassId] = useState<string>("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const [editing, setEditing] = useState<any | null>(null);
  const [purge, setPurge] = useState<any | null>(null);
  const historyId = params.get("student");
  const { data: classes } = useApi<any[]>("/classes");
  const { data, error, loading, reload } = useApi<any>(`/students?page=${page}&size=25${classId ? `&class_id=${classId}` : ""}${dq ? `&q=${encodeURIComponent(dq)}` : ""}`);

  const doPurge = async () => {
    try {
      await api(`/students/${purge.id}?purge=true`, { method: "DELETE" });
      toast.success(t("common.saved"));
      setPurge(null);
      reload();
    } catch (e: any) { toast.error(e.message); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.students")} actions={<Button onClick={() => setEditing({})}><Plus /> {t("stu.new")}</Button>} />
      <div className="flex flex-wrap gap-2">
        <Input className="w-full sm:w-72" placeholder={t("common.search")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <Select className="w-full sm:w-48" value={classId} onChange={(e) => { setClassId(e.target.value); setPage(1); }}>
          <option value="">{t("stu.allClasses")}</option>
          {classes?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </div>
      {error ? <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} /> : loading && !data ? <Skeleton className="h-96" /> : !data?.items?.length ? <EmptyState title={t("common.empty")} /> : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <THead><TR><TH>{t("stu.name")}</TH><TH>{t("common.class")}</TH><TH>{t("stu.gender")}</TH><TH>{t("stu.code")}</TH><TH className="text-right">{t("common.actions")}</TH></TR></THead>
                <TBody>
                  {data.items.map((s: any) => (
                    <TR key={s.id}>
                      <TD><button type="button" className="font-medium hover:underline" onClick={() => router.replace(`${pathname}?student=${s.id}`)}>{s.full_name}</button></TD>
                      <TD>{s.class_name ?? "—"}</TD>
                      <TD>{s.gender === "f" ? t("stu.female") : s.gender === "m" ? t("stu.male") : "—"}</TD>
                      <TD className="font-mono text-xs">{s.student_code}</TD>
                      <TD className="whitespace-nowrap text-right">
                        <Button size="icon" variant="ghost" aria-label={t("common.edit")} onClick={() => setEditing(s)}><Pencil /></Button>
                        <Button size="icon" variant="ghost" aria-label={t("stu.export")} onClick={() => download(`/api/students/${s.id}/export`)}><Download /></Button>
                        <Button size="icon" variant="ghost" aria-label={t("stu.purge")} onClick={() => setPurge(s)}><UserX className="text-destructive" /></Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
            <Pagination page={page} size={25} total={data.total} onPage={setPage} labels={{ prev: t("common.prev"), next: t("common.next") }} />
          </CardContent>
        </Card>
      )}
      {editing ? <StudentForm initial={editing} classes={classes ?? []} onClose={() => setEditing(null)} onSaved={reload} /> : null}
      {historyId ? <HistoryDialog id={Number(historyId)} onClose={() => router.replace(pathname)} /> : null}
      {purge ? (
        <Dialog open onOpenChange={(o) => !o && setPurge(null)}>
          <DialogContent title={t("stu.purge")} description={purge.full_name}>
            <p className="text-sm">{t("stu.purgeConfirm")}</p>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPurge(null)}>{t("common.cancel")}</Button>
              <Button variant="destructive" onClick={doPurge}><Trash2 /> {t("common.delete")}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  );
}

export default function StudentsPage() {
  return <Suspense><Inner /></Suspense>;
}
