"use client";
import { ChevronDown, ChevronRight, Download, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input, Switch } from "@/components/ui/input";
import { ErrorState, Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type UStudent = { id: number; full_name: string; gender: string | null; imported: boolean; planit_class: string | null };
type UClass = { id: number; name: string; planit_class_id: number | null; planit_class_name: string | null; students: UStudent[] };
type Roster = { school?: { name?: string }; school_code?: string; year?: string; classes: UClass[] };

/** Platform admins belong to no school: they choose which school (iMARLEN ID code) to import. */
function SchoolCode({ value, onApply }: { value: string; onApply: (code: string) => void }) {
  const { t } = useI18n();
  const { data } = useApi<{ schools?: { id: number; name: string; idp_code: string }[] }>("/integrations/ustaz/status");
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <Input list="ustaz-schools" className="font-mono sm:w-56" value={v} onChange={(e) => setV(e.target.value)} placeholder={t("ustaz.schoolCode")} aria-label={t("ustaz.schoolCode")} onKeyDown={(e) => { if (e.key === "Enter" && v.trim()) onApply(v.trim()); }} />
      <datalist id="ustaz-schools">{data?.schools?.map((s) => <option key={s.id} value={s.idp_code}>{s.name}</option>)}</datalist>
      <Button variant="outline" disabled={!v.trim() || v.trim() === value} onClick={() => onApply(v.trim())}>{t("ustaz.load")}</Button>
      <span className="text-xs text-muted-foreground">{t("ustaz.schoolHint")}</span>
    </div>
  );
}

function Check({ state, onChange, label }: { state: boolean | "mixed"; onChange: (v: boolean) => void; label: string }) {
  return (
    <input
      type="checkbox"
      aria-label={label}
      className="size-4 shrink-0 cursor-pointer accent-[hsl(var(--primary))]"
      checked={state === true}
      ref={(el) => { if (el) el.indeterminate = state === "mixed"; }}
      onChange={(e) => onChange(e.target.checked)}
      onClick={(e) => e.stopPropagation()}
    />
  );
}

function Picker({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const platformAdmin = user?.role === "admin";
  const [code, setCode] = useState("");
  const { data, error, loading, reload } = useApi<Roster>(`/integrations/ustaz/roster${code ? `?school_code=${encodeURIComponent(code)}` : ""}`);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [open, setOpen] = useState<Set<number>>(new Set());
  const [q, setQ] = useState("");
  const [onlyNew, setOnlyNew] = useState(true);
  const [busy, setBusy] = useState(false);

  const classes = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.classes ?? [])
      .map((c) => {
        const classHit = needle && c.name.toLowerCase().includes(needle);
        const students = c.students.filter((s) => (!onlyNew || !s.imported) && (!needle || classHit || s.full_name.toLowerCase().includes(needle)));
        return { ...c, students };
      })
      .filter((c) => c.students.length > 0);
  }, [data, q, onlyNew]);

  const toggle = (ids: number[], on: boolean) =>
    setPicked((p) => {
      const n = new Set(p);
      ids.forEach((id) => (on ? n.add(id) : n.delete(id)));
      return n;
    });
  const stateOf = (ids: number[]): boolean | "mixed" => {
    const k = ids.filter((id) => picked.has(id)).length;
    return k === 0 ? false : k === ids.length ? true : "mixed";
  };
  const visibleIds = classes.flatMap((c) => c.students.map((s) => s.id));
  const searching = q.trim().length > 0;

  const run = async () => {
    setBusy(true);
    try {
      const r = await api<any>("/integrations/ustaz/import", { method: "POST", json: { student_ids: [...picked], school_code: platformAdmin ? data?.school_code ?? (code || null) : null } });
      const parts = [t("ustaz.created", { n: r.created })];
      if (r.linked) parts.push(t("ustaz.linked", { n: r.linked }));
      if (r.updated) parts.push(t("ustaz.updated", { n: r.updated }));
      if (r.classes_created) parts.push(t("ustaz.classesCreated", { n: r.classes_created }));
      toast.success(parts.join(" · "));
      onDone();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  const apply = (c: string) => { setPicked(new Set()); setCode(c); };
  const codeRow = platformAdmin ? <SchoolCode value={data?.school_code ?? code} onApply={apply} /> : null;
  if (error) return <>{codeRow}<ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} /></>;
  if (loading && !data) return <>{codeRow}<div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div></>;

  return (
    <>
      {codeRow}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("ustaz.search")} />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Switch checked={onlyNew} onChange={setOnlyNew} label={t("ustaz.onlyNew")} />
          <span>{t("ustaz.onlyNew")}</span>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm text-muted-foreground">
        <label className="flex cursor-pointer items-center gap-2">
          <Check state={visibleIds.length ? stateOf(visibleIds) : false} onChange={(v) => toggle(visibleIds, v)} label={t("ustaz.all")} />
          {t("ustaz.all")}
        </label>
        {data?.year ? <span>{data.school?.name ? `${data.school.name} · ` : ""}{data.year}</span> : null}
      </div>
      <div className="max-h-[50vh] divide-y overflow-y-auto rounded-md border" data-testid="ustaz-roster">
        {!classes.length ? (
          <p className="p-6 text-center text-sm text-muted-foreground">{onlyNew && data?.classes.length ? t("ustaz.allIn") : t("common.empty")}</p>
        ) : classes.map((c) => {
          const ids = c.students.map((s) => s.id);
          const expanded = searching || open.has(c.id);
          const k = ids.filter((id) => picked.has(id)).length;
          return (
            <div key={c.id}>
              <div
                className="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-muted/50"
                onClick={() => setOpen((o) => { const n = new Set(o); if (n.has(c.id)) n.delete(c.id); else n.add(c.id); return n; })}
              >
                <Check state={stateOf(ids)} onChange={(v) => toggle(ids, v)} label={c.name} />
                {expanded ? <ChevronDown className="size-4 text-muted-foreground" /> : <ChevronRight className="size-4 text-muted-foreground" />}
                <span className="font-medium">{c.name}</span>
                <span className="text-xs text-muted-foreground">{c.students.length} {t("cls.students")}</span>
                {c.planit_class_id ? <Badge variant="secondary" className="ml-auto">{t("ustaz.inPlanit", { c: c.planit_class_name ?? "" })}</Badge>
                  : <Badge variant="outline" className="ml-auto">{t("ustaz.newClass")}</Badge>}
                {k > 0 ? <Badge>{k}</Badge> : null}
              </div>
              {expanded ? (
                <ul className="pb-1">
                  {c.students.map((s) => (
                    <li key={s.id}>
                      <label className={cn("flex cursor-pointer items-center gap-3 py-1.5 pl-10 pr-3 text-sm hover:bg-muted/40", s.imported && "text-muted-foreground")}>
                        <Check state={picked.has(s.id)} onChange={(v) => toggle([s.id], v)} label={s.full_name} />
                        <span className="flex-1">{s.full_name}</span>
                        {s.imported ? <Badge variant="success">{t("ustaz.already")}</Badge> : null}
                      </label>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>
      <DialogFooter>
        <span className="mr-auto self-center text-sm text-muted-foreground">{t("ustaz.picked", { n: picked.size })}</span>
        <Button onClick={run} disabled={!picked.size} loading={busy}><Download /> {t("ustaz.import")}</Button>
      </DialogFooter>
    </>
  );
}

/** «Ұстаздан импорттау» button: pick classes / students from the school's Ustaz journal and add them to Planit. */
export function UstazImport({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button variant="outline"><Download /> {t("ustaz.button")}</Button></DialogTrigger>
      <DialogContent wide title={t("ustaz.title")} description={t("ustaz.hint")}>
        {open ? <Picker onDone={() => { setOpen(false); onDone(); }} /> : null}
      </DialogContent>
    </Dialog>
  );
}
