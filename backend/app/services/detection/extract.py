"""Answer extraction from aligned template pages: OMR for bubbles, region OCR for written answers."""
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.services.ocr import OCRService

LATIN_TYPES = {"numeric", "formula", "matching", "table"}


@dataclass
class Extracted:
    question_id: int | None
    number: int
    text: str
    raw_text: str
    confidence: float  # 0..1
    bbox: dict
    flags: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def _px(region: dict, W: int, H: int, pad: float = 0.0):
    x, y, w, h = region["x"] * W, region["y"] * H, region["w"] * W, region["h"] * H
    return int(x + pad), int(y + pad), int(w - 2 * pad), int(h - 2 * pad)


def bubble_fill(gray: np.ndarray, cx: float, cy: float, r: float) -> float:
    """Dark-pixel ratio inside the inner 70% of a bubble."""
    H, W = gray.shape
    x, y, rr = int(cx * W), int(cy * H), max(2, int(r * W * 0.7))
    patch = gray[max(0, y - rr):y + rr, max(0, x - rr):x + rr]
    if patch.size == 0:
        return 0.0
    mask = np.zeros_like(patch, dtype=np.uint8)
    cv2.circle(mask, (patch.shape[1] // 2, patch.shape[0] // 2), rr, 255, -1)
    dark = (patch < 128) & (mask > 0)
    return float(dark.sum()) / max(1, int((mask > 0).sum()))


def read_bubbles(gray: np.ndarray, region: dict) -> Extracted:
    fills = {b["label"]: bubble_fill(gray, b["cx"], b["cy"], b["r"]) for b in region["bubbles"]}
    ranked = sorted(fills.items(), key=lambda kv: kv[1], reverse=True)
    marked = [k for k, v in fills.items() if v >= 0.35]
    flags = []
    top = ranked[0][1] if ranked else 0
    second = ranked[1][1] if len(ranked) > 1 else 0
    if not marked:
        flags.append("empty")
        conf = 0.95 if top < 0.15 else 0.6
        text = ""
    else:
        text = ",".join(sorted(marked))
        if region["answer_type"] == "single_choice" and len(marked) > 1:
            flags.append("multiple_marks")
        # separation between marked and unmarked fills drives confidence
        unmarked_max = max([v for k, v in fills.items() if k not in marked], default=0)
        sep = min(fills[k] for k in marked) - unmarked_max
        conf = float(max(0.5, min(0.995, 0.6 + sep)))
    return Extracted(region.get("question_id"), region["number"], text, text, conf, _bbox(region), flags,
                     {"fills": {k: round(v, 3) for k, v in fills.items()}, "top": top, "second": second})


def _bbox(region: dict) -> dict:
    return {"x": region["x"], "y": region["y"], "w": region["w"], "h": region["h"]}


def clean_box(crop: np.ndarray) -> np.ndarray:
    """Remove the printed box border so OCR sees only handwriting."""
    c = crop.copy()
    h, w = c.shape
    b = max(4, int(min(h, w) * 0.06))
    c[:b, :] = 255
    c[-b:, :] = 255
    c[:, :b] = 255
    c[:, -b:] = 255
    return c


def ink_ratio(crop: np.ndarray) -> float:
    return float((crop < 110).mean())


def read_text_region(gray: np.ndarray, region: dict, ocr: OCRService) -> Extracted:
    H, W = gray.shape
    x, y, w, h = _px(region, W, H)
    crop = clean_box(gray[y:y + h, x:x + w])
    ink = ink_ratio(crop)
    if ink < 0.0004:
        return Extracted(region.get("question_id"), region["number"], "", "", 0.95, _bbox(region), ["empty"],
                         {"ink": ink})
    # tight crop around the ink + binarisation gives Tesseract a clean, line-like input
    ys, xs = np.where(crop < 110)
    pad = 12
    oy, ox = max(0, ys.min() - pad), max(0, xs.min() - pad)
    tight = crop[oy:ys.max() + pad, ox:xs.max() + pad]
    tight = cv2.threshold(tight, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    tight = cv2.copyMakeBorder(tight, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    latin = region["answer_type"] in LATIN_TYPES
    lines_est = max(1, round(tight.shape[0] / 60))
    mode = "line" if lines_est == 1 else "block"
    scale = 1.5 if tight.shape[0] < 120 else 1.0
    up = cv2.resize(tight, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if scale != 1 else tight
    x, y = x + ox - 20, y + oy - 20  # word boxes are relative to the padded tight crop
    try:
        out = ocr.recognize(up, mode=mode, languages="eng" if latin else None)
    except Exception as e:
        return Extracted(region.get("question_id"), region["number"], "", "", 0.0, _bbox(region), ["unreadable", "error"],
                         {"error": str(e)[:300]})
    text = out.text.strip()
    flags = []
    if not text:
        flags.append("unreadable")
    conf = out.mean_confidence if text else 0.2
    words = [{"text": w.text, "conf": round(w.conf, 3),
              "bbox": [round((x + w.bbox[0] / scale) / W, 5), round((y + w.bbox[1] / scale) / H, 5),
                       round(w.bbox[2] / scale / W, 5), round(w.bbox[3] / scale / H, 5)]} for w in out.words]
    return Extracted(region.get("question_id"), region["number"], text, out.text, float(conf), _bbox(region), flags,
                     {"ink": round(ink, 4), "words": words, "provider": out.provider})


def extract_from_template(gray: np.ndarray, regions: list[dict], ocr: OCRService) -> list[Extracted]:
    out = []
    for r in regions:
        out.append(read_bubbles(gray, r) if r["kind"] == "bubbles" else read_text_region(gray, r, ocr))
    return out
