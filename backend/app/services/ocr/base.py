"""OCR provider abstraction."""
from dataclasses import dataclass, field
from typing import Literal, Protocol

import numpy as np

Mode = Literal["page", "block", "line", "word", "digits"]


@dataclass
class OCRWord:
    text: str
    conf: float  # 0..1
    bbox: tuple[int, int, int, int]  # x, y, w, h in pixels
    line: int = 0
    block: int = 0


@dataclass
class OCROutput:
    text: str
    words: list[OCRWord] = field(default_factory=list)
    mean_confidence: float = 0.0  # 0..1
    provider: str = ""
    duration_ms: int = 0

    def lines(self) -> list[tuple[str, tuple[int, int, int, int], float]]:
        groups: dict[tuple[int, int], list[OCRWord]] = {}
        for w in self.words:
            groups.setdefault((w.block, w.line), []).append(w)
        out = []
        for ws in groups.values():
            x = min(w.bbox[0] for w in ws)
            y = min(w.bbox[1] for w in ws)
            x2 = max(w.bbox[0] + w.bbox[2] for w in ws)
            y2 = max(w.bbox[1] + w.bbox[3] for w in ws)
            out.append((" ".join(w.text for w in ws), (x, y, x2 - x, y2 - y), sum(w.conf for w in ws) / len(ws)))
        return sorted(out, key=lambda t: (t[1][1], t[1][0]))


class OCRProvider(Protocol):
    name: str

    def recognize(self, image: np.ndarray, languages: str, mode: Mode = "page") -> OCROutput: ...
