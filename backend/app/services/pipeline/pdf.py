"""Splitting uploads into page images."""
import numpy as np
import pymupdf as fitz

from app.services.preprocessing import decode_image


class CorruptedFile(ValueError):
    pass


def split_pages(data: bytes, mime: str, dpi: int = 200) -> list[np.ndarray]:
    if mime == "application/pdf":
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            raise CorruptedFile(f"PDF ашылмады: {e}") from e
        if doc.needs_pass:
            raise CorruptedFile("PDF құпиясөзбен қорғалған")
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            pages.append(img[:, :, ::-1].copy())  # RGB → BGR
        if not pages:
            raise CorruptedFile("PDF ішінде бет жоқ")
        return pages
    try:
        return [decode_image(data)]
    except ValueError as e:
        raise CorruptedFile(str(e)) from e
