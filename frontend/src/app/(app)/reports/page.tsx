"use client";
import { FileDown, FileSpreadsheet, FileText, FileType2 } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";
import { ChooseAssessment, ScopePicker, useAssessmentParam } from "@/components/assessment-scope";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader, Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { download } from "@/lib/utils";

function Inner() {
  const { t } = useI18n();
  const [id, setId] = useAssessmentParam();
  const [pdf, setPdf] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    let url: string | null = null;
    setLoading(true);
    setPdf(null);
    api<Blob>(`/exports/assessments/${id}.pdf?inline=true`)
      .then((b) => { url = URL.createObjectURL(new Blob([b], { type: "application/pdf" })); setPdf(url); })
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [id]);

  const items = [
    { icon: FileSpreadsheet, label: t("rep.excel"), href: `/api/exports/assessments/${id}.xlsx`, hint: "Нәтижелер · Ведомость · Талдау · Сынып журналы" },
    { icon: FileSpreadsheet, label: t("rep.gradebook"), href: `/api/exports/assessments/${id}.xlsx?kind=gradebook`, hint: "Электрондық журналға импорт" },
    { icon: FileText, label: t("rep.pdf"), href: `/api/exports/assessments/${id}.pdf`, hint: "Диаграммалармен" },
    { icon: FileType2, label: t("rep.word"), href: `/api/exports/assessments/${id}.docx`, hint: "Өңделетін есеп" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("rep.title")} actions={<ScopePicker value={id} onChange={setId} />} />
      {!id ? (
        <ChooseAssessment />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            {items.map((it) => (
              <Card key={it.label}>
                <CardHeader className="flex flex-row items-center gap-3 space-y-0 p-4">
                  <it.icon className="size-8 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-sm">{it.label}</CardTitle>
                    <CardDescription className="text-xs">{it.hint}</CardDescription>
                  </div>
                  <Button size="icon" variant="outline" onClick={() => download(it.href)} aria-label={t("common.download")}><FileDown /></Button>
                </CardHeader>
              </Card>
            ))}
          </div>
          <Card className="overflow-hidden">
            <CardHeader className="pb-2"><CardTitle className="text-base">{t("rep.preview")}</CardTitle></CardHeader>
            <CardContent className="p-0">
              {loading || !pdf ? <Skeleton className="m-4 h-[70vh]" /> : <iframe title={t("rep.preview")} src={pdf} className="h-[75vh] w-full border-0 bg-muted" />}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export default function ReportsPage() {
  return <Suspense><Inner /></Suspense>;
}
