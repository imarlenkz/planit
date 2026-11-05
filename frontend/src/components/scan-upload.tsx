"use client";
import { Camera, CheckCircle2, FileDown, FileUp, Loader2, Play, QrCode, UploadCloud, X, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/misc";
import { api, wsUrl } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { cn, download } from "@/lib/utils";

const STAGES = ["uploading", "preprocessing", "ocr", "detecting_tasks", "extracting_answers", "evaluating", "done"];

export function useJobProgress(jobId: number | null, onDone?: (job: any) => void) {
  const [job, setJob] = useState<any>(null);
  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    let ws: WebSocket | null = null;
    let timer: any;
    const finish = (j: any) => {
      setJob(j);
      if (j.status === "done" || j.status === "failed") {
        stop = true;
        onDone?.(j);
      }
    };
    const poll = async () => {
      if (stop) return;
      try {
        finish(await api(`/jobs/${jobId}`));
      } catch {}
      if (!stop) timer = setTimeout(poll, 1200);
    };
    try {
      ws = new WebSocket(wsUrl(`/ws/jobs/${jobId}`));
      ws.onmessage = (e) => finish(JSON.parse(e.data));
      ws.onerror = () => {
        ws?.close();
        ws = null;
        poll();
      };
      ws.onclose = () => {
        if (!stop && ws) poll();
      };
    } catch {
      poll();
    }
    return () => {
      stop = true;
      ws?.close();
      clearTimeout(timer);
    };
  }, [jobId]);
  return job;
}

export function JobProgress({ job, uploadPct }: { job: any; uploadPct?: number }) {
  const { t } = useI18n();
  const stage = job?.stage ?? "uploading";
  const idx = STAGES.indexOf(stage);
  const failed = job?.status === "failed";
  const pct = job ? job.progress : (uploadPct ?? 0) * 0.05;
  const s = job?.stats?.by_review_status;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-medium">
          {failed ? <XCircle className="size-4 text-destructive" /> : job?.status === "done" ? <CheckCircle2 className="size-4 text-success" /> : <Loader2 className="size-4 animate-spin text-primary" />}
          {failed ? t("scan.failed") : t(`scan.stage.${stage}` as MessageKey)}
          {job?.total_pages ? <span className="text-muted-foreground">· {job.processed_pages}/{job.total_pages} {t("scan.pages")}</span> : null}
        </span>
        <span className="tabular text-muted-foreground">{Math.round(pct)}%</span>
      </div>
      <Progress value={pct} tone={failed ? "destructive" : job?.status === "done" ? "success" : "primary"} />
      <ol className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4 lg:grid-cols-7">
        {STAGES.map((st, i) => (
          <li key={st} className={cn("flex items-center gap-1.5 rounded-md border px-2 py-1.5", i < idx || job?.status === "done" ? "border-success/30 bg-success/5 text-success" : i === idx && !failed ? "border-primary/40 bg-primary/5 text-primary" : "text-muted-foreground")}>
            {i < idx || job?.status === "done" ? <CheckCircle2 className="size-3.5" /> : i === idx && !failed ? <Loader2 className="size-3.5 animate-spin" /> : <span className="size-3.5 rounded-full border" />}
            {t(`scan.stage.${st}` as MessageKey)}
          </li>
        ))}
      </ol>
      {failed && job?.error ? <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{job.error}</p> : null}
      {job?.status === "done" && s ? (
        <div className="rounded-md border bg-muted/30 p-3 text-sm">
          <p>
            <b>{job.stats.submissions}</b> {t("scan.works")} ·{" "}
            {t("scan.summary", { answers: job.stats.answers, auto: s.auto_approved ?? 0, medium: s.medium ?? 0, review: s.needs_review ?? 0 })}
          </p>
          {job.stats.students_unknown ? <p className="mt-1 text-warning">{t("sub.unknown")}: {job.stats.students_unknown}</p> : null}
          {job.stats.file_errors?.length ? <p className="mt-1 text-destructive">{job.stats.file_errors.join("; ")}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

export function ScanUpload({ assessment, onDone }: { assessment: any; onDone: () => void }) {
  const { t } = useI18n();
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);
  const job = useJobProgress(jobId, (j) => {
    if (j.status === "done") toast.success(t("scan.stage.done"));
    onDone();
  });
  const { data: jobs, reload } = useApi<any[]>(`/assessments/${assessment.id}/jobs`);
  useEffect(() => { if (job?.status === "done" || job?.status === "failed") reload(); }, [job?.status]);

  const add = (list: FileList | null) => {
    if (!list) return;
    const ok = Array.from(list).filter((f) => /\.(pdf|jpe?g|png)$/i.test(f.name) || /^(image\/(jpeg|png)|application\/pdf)$/.test(f.type));
    if (ok.length < list.length) toast.warning("JPG / PNG / PDF");
    setFiles((p) => [...p, ...ok]);
  };

  function start() {
    if (!files.length) return;
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/assessments/${assessment.id}/uploads`);
    xhr.withCredentials = true;
    const m = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
    if (m) xhr.setRequestHeader("X-CSRF-Token", decodeURIComponent(m[1]));
    xhr.upload.onprogress = (e) => e.lengthComputable && setUploadPct((e.loaded / e.total) * 100);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        setJobId(JSON.parse(xhr.responseText).id);
        setFiles([]);
      } else {
        let msg = xhr.statusText;
        try { msg = JSON.parse(xhr.responseText).detail; } catch {}
        toast.error(msg);
        setUploadPct(null);
      }
    };
    xhr.onerror = () => { toast.error(t("err.network")); setUploadPct(null); };
    setUploadPct(0);
    xhr.send(fd);
  }



  const busy = uploadPct !== null && (!job || (job.status !== "done" && job.status !== "failed"));
  const noKey = !assessment.questions?.length;

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("scan.title")}</CardTitle>
            <CardDescription>{t("scan.dropHint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
              className={cn("flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors", drag ? "border-primary bg-primary/5" : "border-border")}
            >
              <UploadCloud className="size-10 text-primary" />
              <p className="font-medium">{t("scan.drop")}</p>
              <div className="flex flex-wrap justify-center gap-2">
                <Button variant="outline" onClick={() => inputRef.current?.click()} disabled={noKey}><FileUp /> {t("scan.choose")}</Button>
                <Button variant="outline" onClick={() => camRef.current?.click()} disabled={noKey}><Camera /> {t("scan.camera")}</Button>
              </div>
              <input ref={inputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" className="hidden" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
              <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
            </div>
            {noKey ? <p className="text-sm text-warning">{t("key.empty")}</p> : null}
            {files.length ? (
              <ul className="divide-y rounded-md border text-sm">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center gap-2 px-3 py-2">
                    <FileUp className="size-4 text-muted-foreground" />
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="tabular text-xs text-muted-foreground">{(f.size / 1024 / 1024).toFixed(1)} MB</span>
                    <Button variant="ghost" size="icon" className="size-7" onClick={() => setFiles(files.filter((_, j) => j !== i))} aria-label={t("common.delete")}><X /></Button>
                  </li>
                ))}
              </ul>
            ) : null}
            <Button size="lg" className="w-full" onClick={start} disabled={!files.length || busy} loading={uploadPct !== null && !jobId}>
              <Play /> {t("scan.start")}
            </Button>
            {(uploadPct !== null || job) && (jobId || uploadPct !== null) ? <JobProgress job={job} uploadPct={uploadPct ?? 0} /> : null}
            {job?.status === "done" ? (
              <Button asChild variant="success" className="w-full"><Link href={`/review?assessment=${assessment.id}`}>{t("scan.openReview")}</Link></Button>
            ) : null}
          </CardContent>
        </Card>
      </div>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><QrCode className="size-4" /> {t("scan.template")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2">
            <Button variant="outline" disabled={noKey} onClick={() => download(`/api/assessments/${assessment.id}/template.pdf?mode=students`)}><FileDown /> {t("scan.templateStudents")}</Button>
            <Button variant="outline" disabled={noKey} onClick={() => download(`/api/assessments/${assessment.id}/template.pdf?mode=blank`)}><FileDown /> {t("scan.templateBlank")}</Button>
          </CardContent>
        </Card>
        {jobs?.length ? (
          <Card>
            <CardHeader><CardTitle>{t("scan.jobs")}</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {jobs.slice(0, 6).map((j) => (
                <div key={j.id} className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground tabular">#{j.id} · {new Date(j.created_at).toLocaleString()}</span>
                  <span className={cn("text-xs font-medium", j.status === "done" ? "text-success" : j.status === "failed" ? "text-destructive" : "text-primary")}>
                    {j.status === "failed" ? t("scan.failed") : t(`scan.stage.${j.stage}` as MessageKey)} {j.total_pages ? `· ${j.total_pages} ${t("scan.pages")}` : ""}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
