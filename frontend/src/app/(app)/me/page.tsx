"use client";
import { StudentHistory } from "@/components/student-history";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { useApi } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";

export default function MyResults() {
  const { t } = useI18n();
  const { data, error, loading, reload } = useApi<any>("/me/results");
  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.myResults")} description={data?.student ? `${data.student.full_name} · ${data.student.class_name ?? ""}` : undefined} />
      {error ? <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} /> : loading || !data ? <Skeleton className="h-64" /> : (
        <Card><CardContent className="pt-6"><StudentHistory rows={data.results} emptyLabel={t("me.empty")} /></CardContent></Card>
      )}
    </div>
  );
}
