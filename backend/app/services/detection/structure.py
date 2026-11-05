"""Template-free structure detection: find task numbers and answer zones from OCR layout.

Used when the scan was not produced from a Planit template (no markers / QR). Recognises
"1.", "1)", "1-тапсырма", "Задание 1", "Task 1" markers, "Жауабы:/Ответ:/Answer:" lines and
A/B/C/D choices.
"""
import re

from app.services.detection.extract import Extracted
from app.services.evaluation.normalize import normalize_option, similarity
from app.services.ocr.base import OCROutput

TASK_RE = re.compile(r"^\s*(?:(\d{1,2})\s*[-–]?\s*(?:тапсырма|тапс|задание|task)|(?:задание|task|тапсырма)\s*№?\s*(\d{1,2})|"
                     r"№\s*(\d{1,2})|(\d{1,2})\s*[.)]\s+)", re.I)
ANSWER_RE = re.compile(r"(жауабы|жауап|ответ|answer)\s*[:\-–]\s*(.*)$", re.I)


def detect_tasks(ocr: OCROutput, page_w: int, page_h: int, questions: list) -> list[Extracted]:
    lines = ocr.lines()
    markers = []
    for i, (txt, bbox, conf) in enumerate(lines):
        m = TASK_RE.match(txt)
        if m:
            n = int(next(g for g in m.groups() if g))
            if 1 <= n <= 60:
                markers.append((i, n))
    by_num = {q.number: q for q in questions}
    results: list[Extracted] = []
    for k, (i, n) in enumerate(markers):
        if n not in by_num or any(r.number == n for r in results):
            continue
        end = markers[k + 1][0] if k + 1 < len(markers) else len(lines)
        block = lines[i:end]
        q = by_num[n]
        answer_lines: list[str] = []
        confs = []
        explicit = None
        for j, (txt, bbox, conf) in enumerate(block):
            am = ANSWER_RE.search(txt)
            if am:
                explicit = am.group(2).strip()
                rest = [t for t, _, _ in block[j + 1:]]
                answer_lines = [explicit, *rest] if explicit else rest
                confs = [c for _, _, c in block[j:]]
                break
        if explicit is None:
            body = [(t, c) for t, _, c in block[1:]]
            body = [(t, c) for t, c in body if similarity(t, q.text or "") < 0.6]  # drop printed question text
            answer_lines = [t for t, _ in body]
            confs = [c for _, c in body]
        text = "\n".join(x for x in answer_lines if x).strip()
        if q.answer_type in ("single_choice", "multiple_choice"):
            text = normalize_option(text) if q.answer_type == "single_choice" else text
        xs = [b[1] for b in block]
        x0 = min(b[0] for b in xs)
        y0 = min(b[1] for b in xs)
        x1 = max(b[0] + b[2] for b in xs)
        y1 = max(b[1] + b[3] for b in xs)
        conf = (sum(confs) / len(confs) if confs else 0.3) * 0.9  # layout uncertainty penalty
        flags = [] if text else ["empty"]
        results.append(Extracted(q.id, n, text, "\n".join(answer_lines), conf,
                                 {"x": x0 / page_w, "y": y0 / page_h, "w": (x1 - x0) / page_w, "h": (y1 - y0) / page_h},
                                 flags, {"method": "structure_detection"}))
    return results
