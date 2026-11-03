"use client";
import Link from "next/link";
import { TrendLine } from "@/components/charts";
import { LevelBadge, TypeBadge } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useI18n } from "@/lib/i18n";
import { cn, fmt, pctColor } from "@/lib/utils";

export function StudentHistory({ rows, emptyLabel }: { rows: any[]; emptyLabel?: string }) {
  const { t } = useI18n();
  if (!rows.length) return <EmptyState title={emptyLabel ?? t("common.empty")} />;
  const sorted = [...rows].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  return (
    <div className="space-y-4">
      {sorted.length > 1 ? <TrendLine data={sorted.map((r) => ({ ...r, label: r.date }))} x="label" y="percent" height={200} labelFmt={(_l, p) => `${p.subject} · ${p.title}`} /> : null}
      <div className="overflow-x-auto">
        <Table>
          <THead><TR><TH>{t("common.date")}</TH><TH>{t("assess.type")}</TH><TH>{t("assess.title")}</TH><TH>{t("common.subject")}</TH><TH>{t("common.score")}</TH><TH>%</TH><TH>{t("result.level")}</TH><TH /></TR></THead>
          <TBody>
            {rows.map((r) => (
              <TR key={r.result_id}>
                <TD className="whitespace-nowrap text-muted-foreground">{r.date}</TD>
                <TD><TypeBadge type={r.type} /></TD>
                <TD className="font-medium"><Link className="hover:underline" href={`/submissions/${r.submission_id}`}>{r.title}</Link></TD>
                <TD>{r.subject}</TD>
                <TD className="tabular">{fmt(r.total)}/{fmt(r.max)}</TD>
                <TD className={cn("tabular font-semibold", pctColor(r.percent))}>{fmt(r.percent)}%</TD>
                <TD><LevelBadge level={r.level} /></TD>
                <TD>{r.is_final ? <Badge variant="success">{t("result.final")}</Badge> : <Badge variant="secondary">{t("result.provisional")}</Badge>}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    </div>
  );
}
