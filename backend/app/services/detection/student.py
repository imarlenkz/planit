"""Student identification from OCR'd header text by fuzzy matching against the class roster."""
import re
from difflib import SequenceMatcher

from app.services.evaluation.normalize import clean_text

NAME_LABELS = r"(аты[\s-]*жөні|оқушы|фио|ф\.и\.о|name|student|аты)"


def extract_name_candidates(text: str) -> list[str]:
    cands = []
    for line in (text or "").splitlines():
        m = re.search(NAME_LABELS + r"\s*[:\-–]?\s*(.+)", line, flags=re.I)
        if m:
            cands.append(m.group(2))
    return cands or [ln for ln in (text or "").splitlines() if len(ln.split()) in (2, 3)]


def _score(a: str, b: str) -> float:
    a, b = clean_text(a), clean_text(b)
    if not a or not b:
        return 0.0
    direct = SequenceMatcher(None, a, b).ratio()
    ta, tb = sorted(a.split()), sorted(b.split())
    swapped = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    # partial: every roster token appears approximately in candidate
    hits = sum(1 for t in tb if any(SequenceMatcher(None, t, x).ratio() > 0.8 for x in ta))
    partial = hits / len(tb) if tb else 0
    return max(direct, swapped, partial * 0.95)


def match_student(text: str, roster: list[tuple[int, str]]) -> tuple[int | None, float, str | None]:
    """Return (student_id, confidence 0..1, detected_name)."""
    best = (None, 0.0, None)
    for cand in extract_name_candidates(text):
        cand = re.sub(r"[_|]+", " ", cand).strip()
        if len(cand) < 3:
            continue
        for sid, name in roster:
            s = _score(cand, name)
            if s > best[1]:
                best = (sid, s, cand)
    if best[1] < 0.72:
        return None, best[1], best[2]
    return best
