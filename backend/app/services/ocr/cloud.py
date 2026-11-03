"""Cloud OCR providers (handwriting-strong). Enabled via OCR_PROVIDER / OCR_FALLBACKS."""
import base64
import time

import cv2
import httpx
import numpy as np

from app.core.config import settings
from app.services.ocr.base import Mode, OCROutput, OCRWord


def _png_b64(image: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", image)
    return base64.b64encode(buf.tobytes()).decode()


class GoogleVisionProvider:
    name = "google"

    def __init__(self):
        if not settings.GOOGLE_VISION_API_KEY:
            raise RuntimeError("GOOGLE_VISION_API_KEY is not set")

    def recognize(self, image: np.ndarray, languages: str, mode: Mode = "page") -> OCROutput:
        t0 = time.monotonic()
        hints = [{"kaz": "kk", "rus": "ru", "eng": "en"}.get(x, x) for x in languages.split("+")]
        body = {"requests": [{"image": {"content": _png_b64(image)},
                              "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                              "imageContext": {"languageHints": hints}}]}
        r = httpx.post(f"https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_VISION_API_KEY}",
                       json=body, timeout=settings.OCR_TIMEOUT_SEC)
        r.raise_for_status()
        resp = r.json()["responses"][0]
        words: list[OCRWord] = []
        line_no = 0
        for page in resp.get("fullTextAnnotation", {}).get("pages", []):
            for bi, block in enumerate(page.get("blocks", [])):
                for para in block.get("paragraphs", []):
                    line_no += 1
                    for w in para.get("words", []):
                        txt = "".join(s["text"] for s in w.get("symbols", []))
                        v = w["boundingBox"].get("vertices", [])
                        xs = [p.get("x", 0) for p in v]
                        ys = [p.get("y", 0) for p in v]
                        words.append(OCRWord(txt, float(w.get("confidence", 0.8)),
                                             (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), line_no, bi))
        text = resp.get("fullTextAnnotation", {}).get("text", "").strip()
        mean = sum(w.conf for w in words) / len(words) if words else 0.0
        return OCROutput(text, words, mean, self.name, int((time.monotonic() - t0) * 1000))


class AzureReadProvider:
    name = "azure"

    def __init__(self):
        if not (settings.AZURE_VISION_ENDPOINT and settings.AZURE_VISION_KEY):
            raise RuntimeError("AZURE_VISION_ENDPOINT / AZURE_VISION_KEY are not set")

    def recognize(self, image: np.ndarray, languages: str, mode: Mode = "page") -> OCROutput:
        t0 = time.monotonic()
        ok, buf = cv2.imencode(".png", image)
        url = f"{settings.AZURE_VISION_ENDPOINT.rstrip('/')}/computervision/imageanalysis:analyze"
        r = httpx.post(url, params={"api-version": "2024-02-01", "features": "read"}, content=buf.tobytes(),
                       headers={"Ocp-Apim-Subscription-Key": settings.AZURE_VISION_KEY,
                                "Content-Type": "application/octet-stream"}, timeout=settings.OCR_TIMEOUT_SEC)
        r.raise_for_status()
        words: list[OCRWord] = []
        lines_txt = []
        for bi, block in enumerate(r.json().get("readResult", {}).get("blocks", [])):
            for li, line in enumerate(block.get("lines", [])):
                lines_txt.append(line["text"])
                for w in line.get("words", []):
                    poly = w["boundingPolygon"]
                    xs, ys = [p["x"] for p in poly], [p["y"] for p in poly]
                    words.append(OCRWord(w["text"], float(w.get("confidence", 0.8)),
                                         (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), bi * 1000 + li, bi))
        mean = sum(w.conf for w in words) / len(words) if words else 0.0
        return OCROutput("\n".join(lines_txt), words, mean, self.name, int((time.monotonic() - t0) * 1000))
