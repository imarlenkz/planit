"""Scan template generator: printable answer sheets with QR codes, corner markers and answer regions.

The layout is stored in `assessment_versions.template_layout` (normalised coordinates, top-left origin)
so the pipeline can align scanned pages and crop every answer region precisely.
"""
import io
import os
import textwrap

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
MARGIN = 42
MARKER = 18
MARKER_OFF = 18
CANVAS_PX = [1654, 2339]  # 200 dpi raster size of A4

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
FONT_BOLD_CANDIDATES = [p.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf") for p in FONT_CANDIDATES]
FONT_HAND_CANDIDATES = [p.replace("DejaVuSans.ttf", "DejaVuSans-Oblique.ttf") for p in FONT_CANDIDATES] + \
    ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]

_fonts_ready = False


def register_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    for name, cands in (("Sans", FONT_CANDIDATES), ("Sans-Bold", FONT_BOLD_CANDIDATES), ("Hand", FONT_HAND_CANDIDATES)):
        for p in cands:
            if os.path.exists(p):
                pdfmetrics.registerFont(TTFont(name, p))
                break
        else:
            raise RuntimeError("DejaVu fonts not found (install fonts-dejavu-core)")
    _fonts_ready = True


def qr_payload(assessment_id: int, version_id: int, student_id: int | None, page: int) -> str:
    return f"PLNT|a={assessment_id}|v={version_id}|s={student_id or 0}|p={page}"


def parse_qr(data: str) -> dict | None:
    if not data or not data.startswith("PLNT|"):
        return None
    out = {}
    for part in data.split("|")[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = int(v) if v.isdigit() else v
    if not {"a", "v", "p"} <= out.keys():
        return None
    return {"assessment_id": out["a"], "version_id": out["v"], "student_id": out.get("s") or None, "page": out["p"]}


def _norm(x: float, y_top: float, w: float, h: float) -> dict:
    return {"x": round(x / PAGE_W, 5), "y": round(y_top / PAGE_H, 5), "w": round(w / PAGE_W, 5), "h": round(h / PAGE_H, 5)}


ANSWER_HEIGHT = {"numeric": 34, "short_text": 34, "formula": 40, "single_choice": 0, "multiple_choice": 0,
                 "matching": 60, "table": 90, "math": 130, "open": 100, "essay": 220, "graph": 160,
                 "drawing": 160, "handwritten": 120}


def _option_labels(q: dict) -> list[str]:
    opts = q.get("options")
    if isinstance(opts, dict):
        return list(opts.keys())
    if isinstance(opts, list) and opts:
        return [o["label"] if isinstance(o, dict) else str(o) for o in opts]
    return ["A", "B", "C", "D"]


def build_layout(questions: list[dict]) -> dict:
    """questions: [{id, number, text, answer_type, options, max_score}] → layout dict."""
    register_fonts()
    regions = []
    page = 1
    y = MARGIN + 150  # page 1 header height
    max_w = PAGE_W - 2 * MARGIN
    for q in questions:
        lines = textwrap.wrap(f"{q['number']}. {q.get('text') or ''}  ({_fmt(q.get('max_score', 1))} балл)", 95) or [""]
        opts = q.get("options") if isinstance(q.get("options"), dict) else None
        opt_lines = [f"{k}) {v}" for k, v in opts.items()] if opts else []
        is_choice = q["answer_type"] in ("single_choice", "multiple_choice")
        ans_h = 26 if is_choice else ANSWER_HEIGHT.get(q["answer_type"], 80)
        need = 14 * len(lines) + 13 * len(opt_lines) + ans_h + 22
        if y + need > PAGE_H - MARGIN - 30:
            page += 1
            y = MARGIN + 60
        text_y = y
        y += 14 * len(lines) + 13 * len(opt_lines) + 4
        region = {"question_id": q.get("id"), "number": q["number"], "page": page, "answer_type": q["answer_type"],
                  "text_top": round(text_y / PAGE_H, 5), "lines": lines, "option_lines": opt_lines}
        if is_choice:
            labels = _option_labels(q)
            bubbles = []
            bx = MARGIN + 70
            for lab in labels:
                bubbles.append({"label": lab, "cx": round((bx + 9) / PAGE_W, 5), "cy": round((y + 11) / PAGE_H, 5),
                                "r": round(8 / PAGE_W, 5)})
                bx += 60
            region.update({"kind": "bubbles", "bubbles": bubbles, **_norm(MARGIN, y, max_w, ans_h)})
        else:
            region.update({"kind": "text", **_norm(MARGIN, y, max_w, ans_h)})
        regions.append(region)
        y += ans_h + 18
    m = MARKER_OFF + MARKER / 2
    markers = [[m / PAGE_W, m / PAGE_H], [(PAGE_W - m) / PAGE_W, m / PAGE_H],
               [(PAGE_W - m) / PAGE_W, (PAGE_H - m) / PAGE_H], [m / PAGE_W, (PAGE_H - m) / PAGE_H]]
    return {"version": 1, "pages": page, "canvas": CANVAS_PX, "markers": markers, "regions": regions,
            "name_field": _norm(MARGIN + 70, MARGIN + 66, 300, 24), "header_box": _norm(MARGIN, MARGIN, max_w, 120)}


def _fmt(x) -> str:
    return f"{float(x):g}"


def _qr_image(data: str):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _y(top: float) -> float:
    """top-left → reportlab bottom-left."""
    return PAGE_H - top


def draw_sheet(c: canvas.Canvas, layout: dict, meta: dict, assessment_id: int, version_id: int,
               student: dict | None, page: int) -> None:
    register_fonts()
    # corner markers
    for (nx, ny) in layout["markers"]:
        cx, cy = nx * PAGE_W, ny * PAGE_H
        c.rect(cx - MARKER / 2, _y(cy + MARKER / 2), MARKER, MARKER, stroke=0, fill=1)
    # QR (top-right, inside markers)
    qr_size = 74 if page == 1 else 58
    c.drawImage(_qr_image(qr_payload(assessment_id, version_id, student and student.get("id"), page)),
                PAGE_W - MARGIN - qr_size, _y(MARGIN + qr_size), qr_size, qr_size)
    c.setFont("Sans", 8)
    c.drawRightString(PAGE_W - MARGIN, _y(PAGE_H - MARGIN + 6), f"{page}/{layout['pages']}-бет · ID {assessment_id}-{version_id}")
    if page == 1:
        c.setFont("Sans-Bold", 14)
        c.drawString(MARGIN, _y(MARGIN + 16), meta.get("title", ""))
        c.setFont("Sans", 9.5)
        c.drawString(MARGIN, _y(MARGIN + 34), f"{meta.get('school', '')}")
        c.drawString(MARGIN, _y(MARGIN + 50), f"Пән: {meta.get('subject', '')}   Сынып: {meta.get('class', '')}   "
                                               f"Нұсқа: {meta.get('version', '1')}   Күні: {meta.get('date', '')}")
        c.setFont("Sans", 11)
        c.drawString(MARGIN, _y(MARGIN + 84), "Аты-жөні:")
        nf = layout["name_field"]
        c.line(nf["x"] * PAGE_W, _y((nf["y"] + nf["h"]) * PAGE_H), (nf["x"] + nf["w"]) * PAGE_W, _y((nf["y"] + nf["h"]) * PAGE_H))
        if student:
            c.setFont("Sans-Bold", 12)
            c.drawString(nf["x"] * PAGE_W + 4, _y((nf["y"] + nf["h"]) * PAGE_H - 6), student["full_name"])
        c.setFont("Sans", 8)
        c.drawString(MARGIN, _y(MARGIN + 112), f"Максималды балл: {_fmt(meta.get('max_score', 0))}. "
                                               "Жауапты тек жақтауларға жазыңыз; дұрыс нұсқаның шеңберін толық бояңыз.")
        c.line(MARGIN, _y(MARGIN + 122), PAGE_W - MARGIN, _y(MARGIN + 122))
    else:
        c.setFont("Sans", 9)
        c.drawString(MARGIN, _y(MARGIN + 14), f"{meta.get('title', '')} — {student['full_name'] if student else ''}")
    for r in layout["regions"]:
        if r["page"] != page:
            continue
        ty = r["text_top"] * PAGE_H
        c.setFont("Sans", 10)
        for i, line in enumerate(r["lines"]):
            c.drawString(MARGIN, _y(ty + 11 + 14 * i), line)
        oy = ty + 14 * len(r["lines"])
        c.setFont("Sans", 9)
        for i, line in enumerate(r.get("option_lines", [])):
            c.drawString(MARGIN + 14, _y(oy + 10 + 13 * i), line)
        if r["kind"] == "bubbles":
            c.setFont("Sans", 9)
            c.drawString(MARGIN, _y(r["y"] * PAGE_H + 15), "Жауабы:")
            for b in r["bubbles"]:
                cx, cy, rad = b["cx"] * PAGE_W, b["cy"] * PAGE_H, b["r"] * PAGE_W
                c.circle(cx, _y(cy), rad, stroke=1, fill=0)
                c.drawString(cx + rad + 4, _y(cy + 3), b["label"])
        else:
            c.setLineWidth(0.8)
            c.rect(r["x"] * PAGE_W, _y((r["y"] + r["h"]) * PAGE_H), r["w"] * PAGE_W, r["h"] * PAGE_H)


def render_template_pdf(layout: dict, meta: dict, assessment_id: int, version_id: int,
                        students: list[dict] | None = None, overlay=None) -> bytes:
    """One copy per student (QR carries student id), or one blank copy.

    overlay(c, student, page) is an optional hook used by the demo generator to "write" answers.
    """
    register_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(meta.get("title", "Planit"))
    for st in (students or [None]):
        for p in range(1, layout["pages"] + 1):
            draw_sheet(c, layout, meta, assessment_id, version_id, st, p)
            if overlay:
                overlay(c, st, p)
            c.showPage()
    c.save()
    return buf.getvalue()
