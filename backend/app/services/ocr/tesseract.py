"""Local Tesseract OCR provider (kaz+rus+eng) with word-level confidence."""
import os
import time

import numpy as np
import pytesseract

from app.core.config import settings
from app.services.ocr.base import Mode, OCROutput, OCRWord

# one thread per tesseract process: we parallelise across pages instead (avoids CPU oversubscription)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

PSM = {"page": 3, "block": 6, "line": 7, "word": 8, "digits": 7}


class TesseractProvider:
    name = "tesseract"

    def recognize(self, image: np.ndarray, languages: str, mode: Mode = "page") -> OCROutput:
        t0 = time.monotonic()
        config = f"--psm {PSM[mode]} --oem 1"
        lang = languages
        if mode == "digits":
            config += " -c tessedit_char_whitelist=0123456789.,-+=/xXyY()<>:"
            lang = "eng"
        data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=pytesseract.Output.DICT,
                                         timeout=settings.OCR_TIMEOUT_SEC)
        words: list[OCRWord] = []
        for i, txt in enumerate(data["text"]):
            txt = (txt or "").strip()
            conf = float(data["conf"][i])
            if not txt or conf < 0:
                continue
            words.append(OCRWord(txt, conf / 100.0, (data["left"][i], data["top"][i], data["width"][i], data["height"][i]),
                                 line=data["block_num"][i] * 1000 + data["par_num"][i] * 100 + data["line_num"][i],
                                 block=data["block_num"][i]))
        lines: dict[int, list[str]] = {}
        for w in words:
            lines.setdefault(w.line, []).append(w.text)
        text = "\n".join(" ".join(v) for _, v in sorted(lines.items()))
        mean = sum(w.conf for w in words) / len(words) if words else 0.0
        return OCROutput(text=text, words=words, mean_confidence=mean, provider=self.name,
                         duration_ms=int((time.monotonic() - t0) * 1000))

    @staticmethod
    def orientation(image: np.ndarray) -> int:
        try:
            osd = pytesseract.image_to_osd(image, config="--psm 0", timeout=20)
            for line in osd.splitlines():
                if line.startswith("Rotate:"):
                    return int(line.split(":")[1])
        except Exception:
            pass
        return 0
