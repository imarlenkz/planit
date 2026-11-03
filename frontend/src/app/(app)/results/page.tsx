"use client";
import { BarChart3, FileSpreadsheet } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";
import { ChooseAssessment, ScopePicker, useAssessmentParam } from "@/components/assessment-scope";
import { ResultsTable } from "@/components/results-table";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/misc";
import { useI18n } from "@/lib/i18n";

function Inner() {
  const { t } = useI18n();
  const [id, setId] = useAssessmentParam();
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.results")}
        actions={
          <>
            <ScopePicker value={id} onChange={setId} />
            {id ? (
              <>
                <Button variant="outline" asChild><Link href={`/analytics?assessment=${id}`}><BarChart3 /> {t("nav.analytics")}</Link></Button>
                <Button variant="outline" asChild><Link href={`/reports?assessment=${id}`}><FileSpreadsheet /> {t("nav.reports")}</Link></Button>
              </>
            ) : null}
          </>
        }
      />
      {id ? <ResultsTable assessmentId={id} /> : <ChooseAssessment />}
    </div>
  );
}

export default function ResultsPage() {
  return <Suspense><Inner /></Suspense>;
}
