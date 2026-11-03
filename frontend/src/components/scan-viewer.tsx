"use client";
import { ChevronLeft, ChevronRight, Crop, Expand, Eye, EyeOff, Maximize2, RotateCw, ScanSearch, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/misc";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type Region = { id: number; number: number; page_id: number | null; bbox: { x: number; y: number; w: number; h: number } | null; tone: "success" | "warning" | "destructive" | "primary" };

const TONE: Record<Region["tone"], string> = {
  success: "border-emerald-500 bg-emerald-500/10",
  warning: "border-amber-500 bg-amber-500/15",
  destructive: "border-rose-500 bg-rose-500/10",
  primary: "border-blue-500 bg-blue-500/10",
};

export function ScanViewer({ pages, regions, selected, onSelect }: { pages: { id: number; page_number: number; width?: number; height?: number }[]; regions: Region[]; selected?: number | null; onSelect?: (id: number) => void }) {
  const { t } = useI18n();
  const [pageIdx, setPageIdx] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [fit, setFit] = useState<"width" | "page">("width");
  const [overlay, setOverlay] = useState(true);
  const [crop, setCrop] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const [boxSize, setBoxSize] = useState({ w: 600, h: 800 });
  const page = pages[pageIdx];
  const ratio = page?.width && page?.height ? page.height / page.width : 1.414;

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setBoxSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // jump to the page that holds the selected answer
  useEffect(() => {
    const r = regions.find((x) => x.id === selected);
    if (r?.page_id) {
      const i = pages.findIndex((p) => p.id === r.page_id);
      if (i >= 0 && i !== pageIdx) setPageIdx(i);
    }
  }, [selected]);

  const sel = regions.find((x) => x.id === selected && x.page_id === page?.id && x.bbox);
  const baseW = fit === "width" ? boxSize.w - 24 : Math.min(boxSize.w - 24, (boxSize.h - 24) / ratio);
  const cropScale = crop && sel?.bbox ? Math.min(4, 0.92 / Math.max(sel.bbox.w, 0.05)) : 1;
  const width = Math.max(200, baseW * zoom * cropScale);
  const height = width * ratio;

  useEffect(() => {
    if (!crop || !sel?.bbox || !box.current) return;
    box.current.scrollTo({ left: sel.bbox.x * width - 12, top: sel.bbox.y * height - 40, behavior: "smooth" });
  }, [crop, selected, width]);

  useEffect(() => {
    if (!sel?.bbox || !box.current || crop) return;
    const top = sel.bbox.y * height - box.current.clientHeight / 3;
    box.current.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }, [selected, pageIdx]);

  const fullscreen = () => {
    const el = box.current?.parentElement;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else el.requestFullscreen?.();
  };

  if (!page) return <div className="grid h-full place-items-center text-sm text-muted-foreground">—</div>;
  const rotated = rotation % 180 !== 0;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border bg-muted/40">
      <div className="flex flex-wrap items-center gap-1 border-b bg-card px-2 py-1.5">
        <Button variant="ghost" size="icon" onClick={() => setPageIdx(Math.max(0, pageIdx - 1))} disabled={pageIdx === 0} aria-label={t("common.prev")}><ChevronLeft /></Button>
        <span className="min-w-14 text-center text-sm tabular">{pageIdx + 1} / {pages.length}</span>
        <Button variant="ghost" size="icon" onClick={() => setPageIdx(Math.min(pages.length - 1, pageIdx + 1))} disabled={pageIdx >= pages.length - 1} aria-label={t("common.next")}><ChevronRight /></Button>
        <span className="mx-1 h-5 w-px bg-border" />
        <Tooltip content={t("viewer.zoomOut")}><Button variant="ghost" size="icon" onClick={() => setZoom((z) => Math.max(0.4, z / 1.25))}><ZoomOut /></Button></Tooltip>
        <span className="w-12 text-center text-xs tabular">{Math.round(zoom * 100)}%</span>
        <Tooltip content={t("viewer.zoomIn")}><Button variant="ghost" size="icon" onClick={() => setZoom((z) => Math.min(5, z * 1.25))}><ZoomIn /></Button></Tooltip>
        <Tooltip content={t("viewer.rotate")}><Button variant="ghost" size="icon" onClick={() => setRotation((r) => (r + 90) % 360)}><RotateCw /></Button></Tooltip>
        <Tooltip content={t("viewer.fitWidth")}><Button variant={fit === "width" ? "secondary" : "ghost"} size="icon" onClick={() => { setFit("width"); setZoom(1); }}><Expand /></Button></Tooltip>
        <Tooltip content={t("viewer.fitPage")}><Button variant={fit === "page" ? "secondary" : "ghost"} size="icon" onClick={() => { setFit("page"); setZoom(1); }}><ScanSearch /></Button></Tooltip>
        <Tooltip content={t("viewer.crop")}><Button variant={crop ? "secondary" : "ghost"} size="icon" onClick={() => setCrop((c) => !c)} disabled={!sel}><Crop /></Button></Tooltip>
        <Tooltip content={t("viewer.overlay")}><Button variant={overlay ? "secondary" : "ghost"} size="icon" onClick={() => setOverlay((o) => !o)}>{overlay ? <Eye /> : <EyeOff />}</Button></Tooltip>
        <Tooltip content={t("viewer.fullscreen")}><Button variant="ghost" size="icon" className="ml-auto" onClick={fullscreen}><Maximize2 /></Button></Tooltip>
      </div>
      <div ref={box} className="relative flex-1 overflow-auto p-3 scrollbar-thin">
        <div className="mx-auto" style={{ width: rotated ? height : width, height: rotated ? width : height }}>
          <div
            className="relative origin-top-left bg-white shadow-md"
            style={{
              width,
              height,
              transform: rotation === 90 ? `translateX(${height}px) rotate(90deg)` : rotation === 180 ? `translate(${width}px, ${height}px) rotate(180deg)` : rotation === 270 ? `translateY(${width}px) rotate(270deg)` : undefined,
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/pages/${page.id}/image`} alt={`${t("common.page")} ${page.page_number}`} className="absolute inset-0 size-full select-none" draggable={false} />
            {overlay
              ? regions.filter((r) => r.page_id === page.id && r.bbox).map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => onSelect?.(r.id)}
                    className={cn("absolute rounded-sm border-2 transition-shadow", TONE[r.tone], r.id === selected ? "ring-4 ring-primary/40" : "opacity-80 hover:opacity-100")}
                    style={{ left: `${r.bbox!.x * 100}%`, top: `${r.bbox!.y * 100}%`, width: `${r.bbox!.w * 100}%`, height: `${r.bbox!.h * 100}%` }}
                    aria-label={`${r.number}`}
                  >
                    <span className="absolute -top-2.5 left-1 rounded bg-foreground px-1 text-[10px] font-semibold leading-4 text-background">{r.number}</span>
                  </button>
                ))
              : null}
          </div>
        </div>
      </div>
    </div>
  );
}
