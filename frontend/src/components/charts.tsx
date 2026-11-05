"use client";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmt } from "@/lib/utils";

const AXIS = { stroke: "hsl(var(--muted-foreground))", fontSize: 12, tickLine: false, axisLine: false } as const;
const GRID = <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="0" />;
const PRIMARY = "hsl(var(--primary))";

function Tip({ active, payload, label, unit = "%", labelFmt }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="mb-0.5 font-medium">{labelFmt ? labelFmt(label, p.payload) : label}</p>
      <p className="tabular">{p.name ? `${p.name}: ` : ""}<b>{fmt(p.value)}{unit}</b></p>
    </div>
  );
}

/** Vertical bars (one series, single hue). Values are percents unless `unit` is overridden. */
export function PercentBars({ data, x, y, name, unit = "%", height = 260, max = 100, colorFor, labelFmt }: { data: any[]; x: string; y: string; name?: string; unit?: string; height?: number; max?: number | "auto"; colorFor?: (d: any) => string; labelFmt?: (l: any, d: any) => string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }} barCategoryGap="20%">
        {GRID}
        <XAxis dataKey={x} {...AXIS} interval={0} />
        <YAxis {...AXIS} domain={[0, max === "auto" ? "auto" : max]} allowDecimals={false} />
        <Tooltip cursor={{ fill: "hsl(var(--muted))", opacity: 0.6 }} content={<Tip unit={unit} labelFmt={labelFmt} />} />
        <Bar dataKey={y} name={name} radius={[4, 4, 0, 0]} maxBarSize={44} fill={PRIMARY}>
          {colorFor ? data.map((d, i) => <Cell key={i} fill={colorFor(d)} />) : null}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Horizontal bars for long category labels (descriptors, objectives, error types). */
export function HBars({ data, label, value, unit = "%", max = 100, height }: { data: any[]; label: string; value: string; unit?: string; max?: number | "auto"; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(120, data.length * 34 + 24)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }} barCategoryGap="22%">
        <CartesianGrid horizontal={false} stroke="hsl(var(--border))" />
        <XAxis type="number" {...AXIS} domain={[0, max === "auto" ? "auto" : max]} allowDecimals={false} />
        <YAxis type="category" dataKey={label} {...AXIS} width={92} />
        <Tooltip cursor={{ fill: "hsl(var(--muted))", opacity: 0.6 }} content={<Tip unit={unit} labelFmt={(l: any, d: any) => d.full ?? l} />} />
        <Bar dataKey={value} radius={[0, 4, 4, 0]} maxBarSize={22} fill={PRIMARY} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TrendLine({ data, x, y, height = 240, labelFmt }: { data: any[]; x: string; y: string; height?: number; labelFmt?: (l: any, d: any) => string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 12, right: 16, left: -16, bottom: 0 }}>
        {GRID}
        <XAxis dataKey={x} {...AXIS} />
        <YAxis {...AXIS} domain={[0, 100]} />
        <Tooltip cursor={{ stroke: "hsl(var(--muted-foreground))", strokeDasharray: "3 3" }} content={<Tip labelFmt={labelFmt} />} />
        <Line type="monotone" dataKey={y} stroke={PRIMARY} strokeWidth={2} dot={{ r: 4, strokeWidth: 2, fill: "hsl(var(--card))" }} activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
