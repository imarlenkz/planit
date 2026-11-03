"use client";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api } from "@/lib/api";
import { isAdmin, useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export default function SubjectsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const admin = isAdmin(user);
  const { data: subjects, reload } = useApi<any[]>("/subjects");
  const [sel, setSel] = useState<number | null>(null);
  const current = sel ?? subjects?.[0]?.id ?? null;
  const { data: objectives, reload: reloadObj } = useApi<any[]>(current ? `/objectives?subject_id=${current}` : null, [current]);
  const [ns, setNs] = useState({ name: "", code: "" });
  const [no, setNo] = useState({ code: "", description: "", grade: "" });

  const run = async (fn: () => Promise<any>, after: () => void) => {
    try { await fn(); toast.success(t("common.saved")); after(); } catch (e: any) { toast.error(e.message); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("subj.title")} />
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card>
          <CardHeader><CardTitle>{t("nav.subjects")}</CardTitle></CardHeader>
          <CardContent className="space-y-1 p-2">
            {!subjects ? <Skeleton className="h-40" /> : subjects.map((s) => (
              <div key={s.id} className={cn("flex items-center gap-2 rounded-md px-2 py-1.5", s.id === current ? "bg-primary/10 text-primary" : "hover:bg-muted")}>
                <button type="button" className="flex-1 text-left text-sm font-medium" onClick={() => setSel(s.id)}>{s.name} <span className="text-xs text-muted-foreground">{s.code}</span></button>
                {admin && s.school_id ? <Button size="icon" variant="ghost" aria-label={t("common.delete")} onClick={() => run(() => api(`/subjects/${s.id}`, { method: "DELETE" }), reload)}><Trash2 className="size-4 text-destructive" /></Button> : null}
              </div>
            ))}
            <div className="flex gap-1 border-t p-1 pt-3">
              <Input placeholder={t("subj.new")} value={ns.name} onChange={(e) => setNs({ ...ns, name: e.target.value })} />
              <Input className="w-20" placeholder={t("common.code")} value={ns.code} onChange={(e) => setNs({ ...ns, code: e.target.value })} />
              <Button size="icon" aria-label={t("common.add")} disabled={!ns.name} onClick={() => run(() => api("/subjects", { method: "POST", json: { name: ns.name, code: ns.code || null } }), () => { setNs({ name: "", code: "" }); reload(); })}><Plus /></Button>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("subj.objectives")}</CardTitle></CardHeader>
          <CardContent className="p-0">
            <Table>
              <THead><TR><TH>{t("common.code")}</TH><TH>{t("common.description")}</TH><TH>{t("cls.grade")}</TH><TH /></TR></THead>
              <TBody>
                {objectives?.map((o) => (
                  <TR key={o.id}>
                    <TD className="font-mono text-xs">{o.code}</TD>
                    <TD>{o.description}</TD>
                    <TD className="tabular">{o.grade ?? "—"}</TD>
                    <TD className="text-right"><Button size="icon" variant="ghost" aria-label={t("common.delete")} onClick={() => run(() => api(`/objectives/${o.id}`, { method: "DELETE" }), reloadObj)}><Trash2 className="size-4 text-destructive" /></Button></TD>
                  </TR>
                ))}
                <TR>
                  <TD><Input className="w-28 font-mono" placeholder="5.1.2.3" value={no.code} onChange={(e) => setNo({ ...no, code: e.target.value })} /></TD>
                  <TD><Input placeholder={t("obj.new")} value={no.description} onChange={(e) => setNo({ ...no, description: e.target.value })} /></TD>
                  <TD><Input className="w-16" type="number" value={no.grade} onChange={(e) => setNo({ ...no, grade: e.target.value })} /></TD>
                  <TD className="text-right"><Button size="icon" aria-label={t("common.add")} disabled={!no.code || !no.description || !current} onClick={() => run(() => api("/objectives", { method: "POST", json: { code: no.code, description: no.description, grade: Number(no.grade) || null, subject_id: current } }), () => { setNo({ code: "", description: "", grade: "" }); reloadObj(); })}><Plus /></Button></TD>
                </TR>
              </TBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
