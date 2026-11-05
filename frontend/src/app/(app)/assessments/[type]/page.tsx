"use client";
import { FileText, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { TypeBadge } from "@/components/common";
import { NewAssessmentDialog } from "@/components/new-assessment";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Pagination, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useApi, useDebounced } from "@/lib/hooks";
import { useI18n, type MessageKey } from "@/lib/i18n";
import { TYPE_SLUG, fmt } from "@/lib/utils";

export default function AssessmentList() {
  const { type: slug } = useParams<{ type: string }>();
  const type = TYPE_SLUG[slug] ?? "BZhB";
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [classId, setClassId] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const { data: classes } = useApi<any[]>("/classes");
  const { data, error, loading, reload } = useApi<any>(
    `/assessments?type=${type}&page=${page}&size=20${dq ? `&q=${encodeURIComponent(dq)}` : ""}${classId ? `&class_id=${classId}` : ""}`,
  );
  const navKey = ({ BZhB: "nav.bzhb", TZhB: "nav.tzhb", AB: "nav.ab" } as Record<string, MessageKey>)[type];
  return (
    <div>
      <PageHeader
        title={t(navKey)}
        description={data ? `${t("common.total")}: ${data.total}` : undefined}
        actions={<NewAssessmentDialog defaultType={type} trigger={<Button><Plus /> {t("dash.newAssessment")}</Button>} />}
      />
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input className="pl-9" placeholder={t("common.search")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
        <Select className="sm:w-48" value={classId} onChange={(e) => { setClassId(e.target.value); setPage(1); }} aria-label={t("common.class")}>
          <option value="">{t("common.all")}</option>
          {classes?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </div>
      {error ? (
        <ErrorState message={error.message} onRetry={reload} retryLabel={t("common.retry")} />
      ) : loading && !data ? (
        <Skeleton className="h-64" />
      ) : !data?.items.length ? (
        <EmptyState icon={FileText} title={t("assess.none")} hint={t("assess.noneHint")} action={<NewAssessmentDialog defaultType={type} trigger={<Button size="sm"><Plus /> {t("dash.newAssessment")}</Button>} />} />
      ) : (
        <>
          <Table>
            <THead>
              <TR>
                <TH>{t("assess.title")}</TH>
                <TH>{t("common.class")}</TH>
                <TH className="hidden md:table-cell">{t("common.subject")}</TH>
                <TH className="hidden md:table-cell">{t("common.date")}</TH>
                <TH className="text-right">{t("assess.maxScore")}</TH>
                <TH className="text-right">{t("assess.submissions")}</TH>
                <TH>{t("common.status")}</TH>
              </TR>
            </THead>
            <TBody>
              {data.items.map((a: any) => (
                <TR key={a.id}>
                  <TD>
                    <Link href={`/assessment/${a.id}`} className="flex items-center gap-2 font-medium hover:text-primary">
                      <TypeBadge type={a.type} /> <span className="line-clamp-1">{a.title}</span>
                    </Link>
                  </TD>
                  <TD>{a.class_name}</TD>
                  <TD className="hidden md:table-cell">{a.subject_name}</TD>
                  <TD className="hidden tabular md:table-cell">{a.date ?? "—"}</TD>
                  <TD className="text-right tabular">{fmt(a.max_score)}</TD>
                  <TD className="text-right tabular">
                    {a.submission_count}
                    {a.needs_review ? <Badge variant="warning" className="ml-2">{a.needs_review}</Badge> : null}
                  </TD>
                  <TD><Badge variant={a.status === "completed" ? "success" : a.status === "active" ? "default" : "secondary"}>{t(`assess.status.${a.status}` as MessageKey)}</Badge></TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <Pagination page={page} size={20} total={data.total} onPage={setPage} labels={{ prev: t("common.prev"), next: t("common.next") }} />
        </>
      )}
    </div>
  );
}
