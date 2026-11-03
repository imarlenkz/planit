"""Generate realistic 'scanned' answer sheets for the demo flow.

Each student's sheet is rendered from the real template (QR + markers), answers are "hand-written"
into the boxes, bubbles are shaded, then the page is rasterised and distorted (rotation, perspective,
shadow, noise, JPEG artefacts) to imitate a phone photo / cheap scanner. Output: one multi-page PDF.
"""
import io
import random

import cv2
import numpy as np
import pymupdf as fitz
from reportlab.lib.colors import Color

from app.services.templates import PAGE_H, PAGE_W, render_template_pdf

INK = Color(0.08, 0.12, 0.45)


def choose_answer(q: dict, ability: float, rng: random.Random) -> str | list:
    r = rng.random()
    if q["answer_type"] in ("single_choice",):
        return q["correct_answer"] if r < ability else rng.choice(q.get("wrong") or ["A"])
    if q["answer_type"] == "multiple_choice":
        return q["correct_answer"] if r < ability else rng.choice(q.get("wrong") or [["A"]])
    if r < ability:
        return rng.choice(q.get("right") or [str(q["correct_answer"])])
    if q.get("partial") and r < ability + (1 - ability) * 0.5:
        return rng.choice(q["partial"])
    if rng.random() < 0.08:
        return ""  # left blank
    return rng.choice(q.get("wrong") or ["?"])


def make_overlay(layout: dict, answers_by_student: dict[int, dict[int, object]], rng: random.Random):
    def overlay(c, student, page):
        if not student:
            return
        ans = answers_by_student.get(student["id"], {})
        for r in layout["regions"]:
            if r["page"] != page:
                continue
            a = ans.get(r["number"])
            if a in (None, "", []):
                continue
            if r["kind"] == "bubbles":
                labels = a if isinstance(a, list) else [a]
                c.setFillColor(INK)
                for b in r["bubbles"]:
                    if b["label"] in labels:
                        cx = b["cx"] * PAGE_W + rng.uniform(-1, 1)
                        cy = PAGE_H - b["cy"] * PAGE_H + rng.uniform(-1, 1)
                        c.ellipse(cx - 6.5, cy - 6, cx + 6.5, cy + 6.5, stroke=0, fill=1)
                c.setFillColor(Color(0, 0, 0))
            else:
                c.setFillColor(INK)
                c.setFont("Hand", 13)
                x0 = r["x"] * PAGE_W + 36 + rng.uniform(0, 8)
                y0 = PAGE_H - r["y"] * PAGE_H - 22
                for i, line in enumerate(str(a).splitlines()):
                    c.drawString(x0, y0 - i * 19, line)
                c.setFillColor(Color(0, 0, 0))
    return overlay


def distort(img: np.ndarray, rng: random.Random, strength: float = 1.0) -> np.ndarray:
    h, w = img.shape[:2]
    # small rotation
    ang = rng.uniform(-2.5, 2.5) * strength
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    img = cv2.warpAffine(img, M, (w, h), borderValue=(250, 250, 250))
    # perspective
    d = 0.02 * strength
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[rng.uniform(0, d) * w, rng.uniform(0, d) * h], [w - rng.uniform(0, d) * w, rng.uniform(0, d) * h],
                      [w - rng.uniform(0, d) * w, h - rng.uniform(0, d) * h], [rng.uniform(0, d) * w, h - rng.uniform(0, d) * h]])
    img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(245, 245, 245))
    # shadow gradient + brightness
    grad = np.tile(np.linspace(1.0, rng.uniform(0.72, 0.9), w, dtype=np.float32), (h, 1))
    if rng.random() < 0.5:
        grad = grad[:, ::-1]
    img = (img.astype(np.float32) * grad[..., None] * rng.uniform(0.92, 1.0)).clip(0, 255)
    # sensor noise
    img = (img + np.random.default_rng(rng.randint(0, 10**6)).normal(0, 6, img.shape)).clip(0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (3, 3), rng.uniform(0.3, 0.8))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(70, 85)])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def phone_photo(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """Put the sheet on a desk background with strong perspective (tests boundary detection)."""
    h, w = img.shape[:2]
    W, H = int(w * 1.25), int(h * 1.2)
    bg = np.full((H, W, 3), (60, 75, 95), np.uint8)
    bg = (bg + np.random.default_rng(1).normal(0, 8, bg.shape)).clip(0, 255).astype(np.uint8)
    ox, oy = (W - w) // 2, (H - h) // 2
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    j = lambda: rng.uniform(-0.04, 0.04) * w  # noqa: E731
    dst = np.float32([[ox + j(), oy + j()], [ox + w + j(), oy + j()], [ox + w + j(), oy + h + j()], [ox + j(), oy + h + j()]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (W, H), borderMode=cv2.BORDER_TRANSPARENT, dst=bg.copy())
    return warped


def generate_demo_scan(layout: dict, meta: dict, assessment_id: int, version_id: int, students: list[dict],
                       questions: list[dict], seed: int = 42, dpi: int = 150) -> bytes:
    rng = random.Random(seed)
    answers = {}
    for i, st in enumerate(students):
        ability = 0.95 if i % 7 == 0 else rng.uniform(0.45, 0.92)
        answers[st["id"]] = {q["number"]: choose_answer(q, ability, rng) for q in questions}
    pdf = render_template_pdf(layout, meta, assessment_id, version_id, students, overlay=make_overlay(layout, answers, rng))
    src = fitz.open(stream=pdf, filetype="pdf")
    out = fitz.open()
    for i, page in enumerate(src):
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3][:, :, ::-1].copy()
        img = distort(img, rng, 1.0)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, stream=buf.tobytes())
    data = io.BytesIO()
    out.save(data, deflate=True)
    return data.getvalue()
