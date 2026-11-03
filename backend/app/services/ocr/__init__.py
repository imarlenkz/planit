"""OCRService: provider selection with fallback chain and timeouts."""
import logging

import numpy as np

from app.core.config import settings
from app.services.ocr.base import Mode, OCROutput, OCRProvider, OCRWord  # noqa: F401

log = logging.getLogger(__name__)


def _make(name: str) -> OCRProvider:
    name = name.strip().lower()
    if name == "google":
        from app.services.ocr.cloud import GoogleVisionProvider
        return GoogleVisionProvider()
    if name == "azure":
        from app.services.ocr.cloud import AzureReadProvider
        return AzureReadProvider()
    from app.services.ocr.tesseract import TesseractProvider
    return TesseractProvider()


class OCRError(RuntimeError):
    pass


class OCRService:
    def __init__(self, providers: list[OCRProvider] | None = None):
        if providers is None:
            providers = []
            for n in [settings.OCR_PROVIDER, *[x for x in settings.OCR_FALLBACKS.split(",") if x.strip()]]:
                try:
                    providers.append(_make(n))
                except Exception as e:
                    log.warning("OCR provider %s unavailable: %s", n, e)
            if not providers:
                providers = [_make("tesseract")]
        self.providers = providers

    @property
    def name(self) -> str:
        return self.providers[0].name

    def recognize(self, image: np.ndarray, mode: Mode = "page", languages: str | None = None) -> OCROutput:
        langs = languages or settings.OCR_LANGUAGES
        errors = []
        for p in self.providers:
            try:
                return p.recognize(image, langs, mode)
            except Exception as e:  # timeout / API error → next provider
                errors.append(f"{p.name}: {e!r}"[:300])
        raise OCRError("; ".join(errors))

    def orientation(self, image: np.ndarray) -> int:
        from app.services.ocr.tesseract import TesseractProvider
        return TesseractProvider.orientation(image)
