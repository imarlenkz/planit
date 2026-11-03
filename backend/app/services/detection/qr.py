"""QR / barcode detection on page images."""
import cv2
import numpy as np

from app.services.templates import parse_qr


def decode_codes(gray: np.ndarray) -> list[dict]:
    out = []
    try:
        from pyzbar import pyzbar

        for scale in (1.0, 0.5, 1.5):
            img = gray if scale == 1.0 else cv2.resize(gray, None, fx=scale, fy=scale)
            for code in pyzbar.decode(img):
                data = code.data.decode("utf-8", "ignore")
                r = code.rect
                out.append({"data": data, "type": code.type,
                            "rect": [int(r.left / scale), int(r.top / scale), int(r.width / scale), int(r.height / scale)]})
            if out:
                break
    except ImportError:
        pass
    if not out:
        det = cv2.QRCodeDetector()
        data, pts, _ = det.detectAndDecode(gray)
        if data:
            x, y = pts[0].min(axis=0)
            x2, y2 = pts[0].max(axis=0)
            out.append({"data": data, "type": "QRCODE", "rect": [int(x), int(y), int(x2 - x), int(y2 - y)]})
    return out


def find_planit_qr(gray: np.ndarray) -> tuple[dict | None, dict | None]:
    """Return (parsed payload, code info). Also reports whether the QR sits in the lower half (upside-down page)."""
    for code in decode_codes(gray):
        parsed = parse_qr(code["data"])
        if parsed:
            h = gray.shape[0]
            code["upside_down"] = code["rect"][1] > h / 2
            return parsed, code
    return None, None
