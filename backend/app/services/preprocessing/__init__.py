"""Image preprocessing before OCR.

Pipeline (each step recorded in `ops` so the UI can show what was done):
boundary detection → perspective correction → crop → 90°/180° rotation fix → deskew →
shadow removal → brightness / contrast (CLAHE) → noise removal → blur reduction → template alignment.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

A4_RATIO = 297 / 210


@dataclass
class Preprocessed:
    image: np.ndarray  # grayscale uint8, enhanced, for OCR/display
    ops: list[str] = field(default_factory=list)
    quality: float = 1.0  # 0..1
    aligned: bool = False
    rotation: float = 0.0
    details: dict = field(default_factory=dict)


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Суретті оқу мүмкін емес (файл бүлінген немесе формат қолдау көрсетілмейді)")
    return img


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise ValueError("PNG encode failed")
    return buf.tobytes()


def encode_jpeg(img: np.ndarray, quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def _limit_size(img: np.ndarray, max_side: int = 2600) -> np.ndarray:
    h, w = img.shape[:2]
    s = max(h, w)
    if s > max_side:
        f = max_side / s
        img = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    return img


def _order_points(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype("float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def detect_document(img: np.ndarray) -> np.ndarray | None:
    """Find the paper sheet quadrilateral in a photo. None when the page already fills the frame."""
    h, w = img.shape[:2]
    scale = 800 / max(h, w)
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_total = small.shape[0] * small.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(c)
        if area < 0.25 * area_total:
            break
        if area > 0.97 * area_total:
            continue  # contour is the frame itself
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return (approx.reshape(4, 2) / scale).astype("float32")
    return None


def warp_quad(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = _order_points(quad)
    wa, wb = np.linalg.norm(br - bl), np.linalg.norm(tr - tl)
    ha, hb = np.linalg.norm(tr - br), np.linalg.norm(tl - bl)
    W, H = int(max(wa, wb)), int(max(ha, hb))
    if H / max(W, 1) < 1.2:  # snap to A4 portrait if close
        H = int(W * A4_RATIO) if abs(H / max(W, 1) - A4_RATIO) < 0.25 else H
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), dst)
    return cv2.warpPerspective(img, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))


def estimate_skew(gray: np.ndarray) -> float:
    """Skew angle in degrees using minAreaRect over text pixels (limited to ±15°)."""
    small = cv2.resize(gray, None, fx=0.5, fy=0.5)
    thr = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3)))
    lines = cv2.HoughLinesP(thr, 1, np.pi / 720, threshold=150, minLineLength=small.shape[1] // 4, maxLineGap=20)
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(a) < 15:
            angles.append(a)
    return float(np.median(angles)) if angles else 0.0


def rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255 if img.ndim == 2 else (255, 255, 255))


def remove_shadows(gray: np.ndarray) -> np.ndarray:
    # background estimate must ignore dark objects (markers, filled bubbles): large max-filter + median
    small = cv2.resize(gray, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    bg = cv2.dilate(small, np.ones((9, 9), np.uint8))
    bg = cv2.medianBlur(bg, 21)
    bg = cv2.resize(bg, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)
    diff = 255 - cv2.absdiff(gray, bg)
    return cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)


def enhance(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def unsharp(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (0, 0), 2)
    return cv2.addWeighted(gray, 1.6, blur, -0.6, 0)


def find_corner_markers(gray: np.ndarray) -> np.ndarray | None:
    """Detect 4 filled black squares near page corners (printed by the Planit template)."""
    h, w = gray.shape
    thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 101, 25)
    contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_side, max_side = 0.012 * w, 0.06 * w
    cands = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if not (min_side <= cw <= max_side and min_side <= ch <= max_side):
            continue
        if not 0.75 <= cw / ch <= 1.33:
            continue
        fill = cv2.contourArea(c) / (cw * ch)
        if fill < 0.8:
            continue
        cands.append((x + cw / 2, y + ch / 2, cw * ch))
    if len(cands) < 4:
        return None
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    chosen = []
    for cx, cy in corners:
        best = min(cands, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        if (best[0] - cx) ** 2 + (best[1] - cy) ** 2 > (0.3 * max(w, h)) ** 2:
            return None
        chosen.append(best[:2])
    pts = np.array(chosen, dtype="float32")
    if len({tuple(p) for p in pts.tolist()}) < 4:
        return None
    return pts


def align_to_template(gray: np.ndarray, markers: np.ndarray, layout: dict) -> np.ndarray:
    """Warp so marker centres land exactly at template positions (normalised coords × canonical size)."""
    W, H = layout.get("canvas", [1654, 2339])
    m = layout["markers"]  # [[x,y] normalised] tl,tr,br,bl
    dst = np.array([[p[0] * W, p[1] * H] for p in m], dtype="float32")
    M = cv2.getPerspectiveTransform(markers, dst)
    return cv2.warpPerspective(gray, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=255)


def preprocess(img: np.ndarray, layout: dict | None = None, detect_orientation=None) -> Preprocessed:
    ops: list[str] = []
    details: dict = {}
    img = _limit_size(img)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    quad = detect_document(img)
    if quad is not None:
        img = warp_quad(img, quad)
        ops += ["document_boundary_detection", "perspective_correction", "crop"]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gray.shape[1] > gray.shape[0] * 1.15:  # landscape photo of portrait sheet
        gray = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
        ops.append("rotation_correction_90")
    if detect_orientation is not None:
        angle = detect_orientation(gray)
        if angle in (90, 180, 270):
            gray = cv2.rotate(gray, {90: cv2.ROTATE_90_COUNTERCLOCKWISE, 180: cv2.ROTATE_180,
                                     270: cv2.ROTATE_90_CLOCKWISE}[angle])
            ops.append(f"rotation_correction_{angle}")

    details["brightness_before"] = round(float(gray.mean()), 1)
    skew = estimate_skew(gray)
    details["skew_deg"] = round(skew, 2)

    aligned = False
    if layout and layout.get("markers"):
        markers = find_corner_markers(gray)
        if markers is None:
            flipped = cv2.rotate(gray, cv2.ROTATE_180)
            m2 = find_corner_markers(flipped)
            if m2 is not None:
                gray, markers = flipped, m2
                ops.append("rotation_correction_180")
        if markers is not None:
            gray = align_to_template(gray, markers, layout)
            ops.append("page_alignment")
            aligned = True
    if not aligned and abs(skew) > 0.3:
        gray = rotate(gray, skew)
        ops.append("deskew")

    gray = remove_shadows(gray)
    ops += ["shadow_removal", "brightness_correction"]
    gray = enhance(gray)
    ops.append("contrast_enhancement")
    gray = cv2.medianBlur(gray, 3)
    ops.append("noise_removal")
    sharp = sharpness(gray)
    details["sharpness"] = round(sharp, 1)
    if sharp < 150:
        gray = unsharp(gray)
        ops.append("blur_reduction")

    contrast = float(gray.std()) / 80.0
    quality = max(0.0, min(1.0, 0.5 * min(1.0, sharp / 300.0) + 0.5 * min(1.0, contrast)))
    return Preprocessed(image=gray, ops=ops, quality=round(quality, 3), aligned=aligned, rotation=skew,
                        details=details)
