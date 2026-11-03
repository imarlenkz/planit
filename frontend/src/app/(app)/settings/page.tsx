"use client";
import { KeyRound, Plus, ShieldCheck } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field, Input, Select, Switch } from "@/components/ui/input";
import { PageHeader, Skeleton } from "@/components/ui/misc";
import { Pagination, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { isAdmin, useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n/messages";

function Profile() {
  const { t, locale, setLocale } = useI18n();
  const { theme, setTheme } = useTheme();
  const { user, refresh } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [pw, setPw] = useState({ old_password: "", new_password: "" });
  const saveProfile = async (patch: any) => {
    try { await api("/auth/me", { method: "PATCH", json: patch }); await refresh(); toast.success(t("common.saved")); } catch (e: any) { toast.error(e.message); }
  };
  const changePw = async () => {
    try { await api("/auth/change-password", { method: "POST", json: pw }); setPw({ old_password: "", new_password: "" }); toast.success(t("common.saved")); } catch (e: any) { toast.error(e.message); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>{t("set.profile")}</CardTitle><CardDescription>{user?.email} · {t(`role.${user?.role}` as MessageKey)}</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          <Field label={t("common.name")}>
            <div className="flex gap-2"><Input value={name} onChange={(e) => setName(e.target.value)} /><Button variant="outline" onClick={() => saveProfile({ full_name: name })} disabled={name.length < 2}>{t("common.save")}</Button></div>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("set.language")}>
              <Select value={locale} onChange={(e) => { const l = e.target.value as Locale; setLocale(l); saveProfile({ locale: l }); }}>
                <option value="kk">Қазақша</option><option value="ru">Русский</option><option value="en">English</option>
              </Select>
            </Field>
            <Field label={t("set.theme")}>
              <Select value={theme ?? "system"} onChange={(e) => setTheme(e.target.value)}>
                <option value="light">{t("theme.light")}</option><option value="dark">{t("theme.dark")}</option><option value="system">{t("theme.system")}</option>
              </Select>
            </Field>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><KeyRound className="size-5" /> {t("set.password")}</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Field label={t("set.oldPassword")}><Input type="password" autoComplete="current-password" value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} /></Field>
          <Field label={t("set.newPassword")} hint="≥ 8"><Input type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
          <Button onClick={changePw} disabled={!pw.old_password || pw.new_password.length < 8}>{t("common.save")}</Button>
        </CardContent>
      </Card>
    </div>
  );
}

function AiSettings() {
  const { t } = useI18n();
  const { data, reload } = useApi<any>("/settings");
  const [f, setF] = useState<any>(null);
  useEffect(() => { if (data) setF(data); }, [data]);
  if (!f) return <Skeleton className="h-80" />;
  const save = async () => {
    const { providers, keys_configured, ...rest } = f;
    try { await api("/settings", { method: "PUT", json: rest }); toast.success(t("common.saved")); reload(); } catch (e: any) { toast.error(e.message); }
  };
  const keyFor: Record<string, string> = { openai: "openai", anthropic: "anthropic", google: "google", azure: "azure" };
  const missing = (p: string) => keyFor[p] && !f.keys_configured?.[keyFor[p]];
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>{t("set.ai")}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Switch checked={f.AI_ENABLED} onChange={(v) => setF({ ...f, AI_ENABLED: v })} label={t("set.aiEnabled")} />
          <Field label={t("set.aiProvider")} hint={missing(f.AI_PROVIDER) ? t("set.keyMissing") : undefined}>
            <Select value={f.AI_PROVIDER} onChange={(e) => setF({ ...f, AI_PROVIDER: e.target.value })}>
              {f.providers.ai.map((p: string) => <option key={p} value={p}>{p}{missing(p) ? " ⚠" : ""}</option>)}
            </Select>
          </Field>
          <Field label={t("set.ocrProvider")} hint={missing(f.OCR_PROVIDER) ? t("set.keyMissing") : undefined}>
            <Select value={f.OCR_PROVIDER} onChange={(e) => setF({ ...f, OCR_PROVIDER: e.target.value })}>
              {f.providers.ocr.map((p: string) => <option key={p} value={p}>{p}{missing(p) ? " ⚠" : ""}</option>)}
            </Select>
          </Field>
          <Field label="OCR languages"><Input value={f.OCR_LANGUAGES} onChange={(e) => setF({ ...f, OCR_LANGUAGES: e.target.value })} /></Field>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{t("set.thresholds")}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("set.high")}><Input type="number" min={50} max={100} value={f.CONFIDENCE_HIGH} onChange={(e) => setF({ ...f, CONFIDENCE_HIGH: Number(e.target.value) })} /></Field>
            <Field label={t("set.medium")}><Input type="number" min={0} max={100} value={f.CONFIDENCE_MEDIUM} onChange={(e) => setF({ ...f, CONFIDENCE_MEDIUM: Number(e.target.value) })} /></Field>
          </div>
          <Switch checked={f.AUTO_APPROVE_HIGH_CONFIDENCE} onChange={(v) => setF({ ...f, AUTO_APPROVE_HIGH_CONFIDENCE: v })} label={t("set.autoApprove")} />
          <p className="pt-2 text-sm font-semibold">{t("set.privacy")}</p>
          <Switch checked={f.AI_SEND_STUDENT_NAMES} onChange={(v) => setF({ ...f, AI_SEND_STUDENT_NAMES: v })} label={t("set.sendNames")} />
          <Switch checked={f.AI_SEND_IMAGES} onChange={(v) => setF({ ...f, AI_SEND_IMAGES: v })} label={t("set.sendImages")} />
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("set.retention")}><Input type="number" min={1} value={f.RETENTION_DAYS} onChange={(e) => setF({ ...f, RETENTION_DAYS: Number(e.target.value) })} /></Field>
            <Field label="Max upload, MB"><Input type="number" min={1} value={f.MAX_UPLOAD_MB} onChange={(e) => setF({ ...f, MAX_UPLOAD_MB: Number(e.target.value) })} /></Field>
          </div>
        </CardContent>
      </Card>
      <div className="lg:col-span-2"><Button onClick={save}>{t("common.save")}</Button></div>
    </div>
  );
}

function Users() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const { data, reload } = useApi<any>(`/users?page=${page}&size=25`);
  const [nu, setNu] = useState<any | null>(null);
  const toggle = async (u: any) => {
    try { await api(`/users/${u.id}`, { method: "PATCH", json: { is_active: !u.is_active } }); reload(); } catch (e: any) { toast.error(e.message); }
  };
  const create = async () => {
    try { await api("/users", { method: "POST", json: nu }); toast.success(t("common.saved")); setNu(null); reload(); } catch (e: any) { toast.error(e.message); }
  };
  const roles = user?.role === "admin" ? ["admin", "school_admin", "teacher", "student"] : ["school_admin", "teacher", "student"];
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>{t("set.users")}</CardTitle>
        <Button size="sm" onClick={() => setNu({ email: "", full_name: "", password: "", role: "teacher", locale: "kk", school_id: user?.school_id ?? null })}><Plus /> {t("set.newUser")}</Button>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <THead><TR><TH>{t("common.name")}</TH><TH>Email</TH><TH>{t("common.role")}</TH><TH>{t("common.active")}</TH></TR></THead>
            <TBody>
              {data?.items?.map((u: any) => (
                <TR key={u.id}>
                  <TD className="font-medium">{u.full_name}</TD>
                  <TD className="text-muted-foreground">{u.email}</TD>
                  <TD><Badge variant="secondary">{t(`role.${u.role}` as MessageKey)}</Badge></TD>
                  <TD><Switch checked={u.is_active} onChange={() => toggle(u)} /></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
        {data ? <Pagination page={page} size={25} total={data.total} onPage={setPage} labels={{ prev: t("common.prev"), next: t("common.next") }} /> : null}
      </CardContent>
      {nu ? (
        <Dialog open onOpenChange={(o) => !o && setNu(null)}>
          <DialogContent title={t("set.newUser")}>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("common.name")} className="sm:col-span-2"><Input value={nu.full_name} onChange={(e) => setNu({ ...nu, full_name: e.target.value })} /></Field>
              <Field label="Email"><Input type="email" value={nu.email} onChange={(e) => setNu({ ...nu, email: e.target.value })} /></Field>
              <Field label={t("auth.password")}><Input type="password" autoComplete="new-password" value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })} /></Field>
              <Field label={t("common.role")}>
                <Select value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}>{roles.map((r) => <option key={r} value={r}>{t(`role.${r}` as MessageKey)}</option>)}</Select>
              </Field>
              <Field label={t("set.language")}>
                <Select value={nu.locale} onChange={(e) => setNu({ ...nu, locale: e.target.value })}><option value="kk">kk</option><option value="ru">ru</option><option value="en">en</option></Select>
              </Field>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setNu(null)}>{t("common.cancel")}</Button>
              <Button onClick={create} disabled={!nu.email || nu.password.length < 8 || nu.full_name.length < 2}>{t("common.create")}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </Card>
  );
}

function Audit() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const { data } = useApi<any>(`/audit?page=${page}&size=50${action ? `&action=${encodeURIComponent(action)}` : ""}`);
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2"><ShieldCheck className="size-5" /> {t("set.audit")}</CardTitle>
        <Input className="w-56" placeholder="review.override" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} />
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <THead><TR><TH>{t("set.when")}</TH><TH>{t("set.user")}</TH><TH>{t("set.action")}</TH><TH>{t("set.entity")}</TH><TH>IP</TH><TH>Δ</TH></TR></THead>
            <TBody>
              {data?.items?.map((r: any) => (
                <TR key={r.id}>
                  <TD className="whitespace-nowrap text-xs text-muted-foreground">{new Date(r.created_at).toLocaleString()}</TD>
                  <TD>{r.user ?? "—"}</TD>
                  <TD className="font-mono text-xs">{r.action}</TD>
                  <TD className="text-xs">{r.entity_type}{r.entity_id ? ` #${r.entity_id}` : ""}</TD>
                  <TD className="text-xs text-muted-foreground">{r.ip}</TD>
                  <TD className="max-w-[320px] truncate font-mono text-[11px] text-muted-foreground" title={JSON.stringify({ before: r.before, after: r.after })}>
                    {r.before || r.after ? `${JSON.stringify(r.before ?? {})} → ${JSON.stringify(r.after ?? {})}` : ""}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
        {data ? <Pagination page={page} size={50} total={data.total} onPage={setPage} labels={{ prev: t("common.prev"), next: t("common.next") }} /> : null}
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const admin = isAdmin(user);
  return (
    <div className="space-y-6">
      <PageHeader title={t("set.title")} />
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">{t("set.profile")}</TabsTrigger>
          {admin ? <><TabsTrigger value="ai">{t("set.ai")}</TabsTrigger><TabsTrigger value="users">{t("set.users")}</TabsTrigger><TabsTrigger value="audit">{t("set.audit")}</TabsTrigger></> : null}
        </TabsList>
        <TabsContent value="profile"><Profile /></TabsContent>
        {admin ? <><TabsContent value="ai"><AiSettings /></TabsContent><TabsContent value="users"><Users /></TabsContent><TabsContent value="audit"><Audit /></TabsContent></> : null}
      </Tabs>
    </div>
  );
}
