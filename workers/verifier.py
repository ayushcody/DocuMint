from __future__ import annotations

import asyncio
import html as html_lib
import io
import logging
import os
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw
from skimage.metrics import structural_similarity

logger = logging.getLogger(__name__)
VERIFIER_PIL_ALLOWED = os.getenv("DOCUMINT_VERIFIER_PIL_FALLBACK", "false").lower() == "true"

_clip_model: object | None = None
_clip_preprocess: object | None = None
_clip_device: str | None = None


async def verify_parse_block(
    original_crop: NDArray[np.uint8],
    predicted_markdown: str,
    predicted_html: str,
    alpha: float = 0.35,
    beta: float = 0.25,
    gamma: float = 0.25,
    delta: float = 0.15,
    flag_threshold: float = 0.15,
) -> dict[str, object]:
    original_bytes = _array_to_png_bytes(original_crop)
    rendered_bytes, is_degraded = await _render_html_to_image(
        predicted_html,
        target_width=max(int(original_crop.shape[1]), 1),
    )
    if is_degraded:
        return {
            "score": 0.5,
            "components": {
                "ssim": 0.0,
                "ocr_consistency": 0.0,
                "layout_iou": 0.0,
                "clip_sim": 0.0,
            },
            "flag_for_repair": True,
            "L_verify": 0.5,
            "degraded": True,
            "degraded_reason": "PIL fallback renderer - install weasyprint or playwright",
        }
    aligned_original, aligned_rendered = _align_sizes(original_bytes, rendered_bytes)

    ssim_score = _compute_ssim(aligned_original, aligned_rendered)
    cer = await _ocr_consistency(rendered_bytes, predicted_markdown.strip())

    orig_boxes = _detect_layout_boxes(aligned_original)
    rend_boxes = _detect_layout_boxes(aligned_rendered)
    layout_iou = _compute_box_set_iou(orig_boxes, rend_boxes)
    clip_sim = await _clip_similarity(original_bytes, rendered_bytes)

    l_verify = (
        alpha * (1 - ssim_score)
        + beta * cer
        + gamma * (1 - layout_iou)
        + delta * (1 - clip_sim)
    )
    return {
        "score": round(max(0.0, min(1.0, 1 - l_verify)), 4),
        "components": {
            "ssim": round(ssim_score, 4),
            "ocr_consistency": round(1 - cer, 4),
            "layout_iou": round(layout_iou, 4),
            "clip_sim": round(clip_sim, 4),
        },
        "flag_for_repair": l_verify > flag_threshold,
        "L_verify": round(l_verify, 4),
    }


async def _render_html_to_image(block_html: str, target_width: int = 800) -> tuple[bytes, bool]:
    full_html = _wrap_html(block_html, target_width)
    try:
        rendered = await asyncio.to_thread(_render_with_weasyprint, full_html)
        if rendered:
            return rendered, False
        logger.warning("WeasyPrint returned an empty render; attempting Playwright HTML rendering")
    except Exception as exc:
        logger.warning(
            "WeasyPrint render failed (%s: %s); attempting Playwright HTML rendering",
            type(exc).__name__,
            exc,
        )

    try:
        return await _render_with_playwright(full_html, target_width), False
    except Exception as exc:
        if not VERIFIER_PIL_ALLOWED:
            logger.error(
                "Playwright render failed (%s: %s). "
                "DOCUMINT_VERIFIER_PIL_FALLBACK=false - hard failing. "
                "Install weasyprint or playwright to fix.",
                type(exc).__name__,
                exc,
            )
            raise RuntimeError(
                "VERIFIER HARD FAIL: WeasyPrint and Playwright both unavailable. "
                "Install weasyprint (pip install weasyprint) or playwright "
                "(pip install playwright && playwright install chromium). "
                "Set DOCUMINT_VERIFIER_PIL_FALLBACK=true to allow degraded PIL rendering "
                "(not recommended - reduces verification accuracy)."
            ) from exc

        logger.error(
            "Playwright render failed (%s: %s). "
            "DOCUMINT_VERIFIER_PIL_FALLBACK=true - using degraded PIL render. "
            "Verification scores will be inaccurate for this block.",
            type(exc).__name__,
            exc,
        )

    rendered = await asyncio.to_thread(_render_with_pil_fallback, block_html, target_width)
    return rendered, True


def _render_with_weasyprint(full_html: str) -> bytes:
    cache_dir = Path(tempfile.gettempdir()) / "documind-font-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))

    from weasyprint import HTML as WeasyHTML  # type: ignore[import-not-found]

    pdf_bytes = WeasyHTML(string=full_html).write_pdf(presentational_hints=True)
    return _pdf_first_page_to_png(bytes(pdf_bytes))


def _pdf_first_page_to_png(pdf_bytes: bytes) -> bytes:
    import fitz  # type: ignore[import-not-found]

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        if document.page_count == 0:
            raise RuntimeError("WeasyPrint produced an empty PDF")
        page = document.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return bytes(pixmap.tobytes("png"))


async def _render_with_playwright(full_html: str, target_width: int) -> bytes:
    try:
        from playwright.async_api import async_playwright  # type: ignore[import-not-found]
    except ImportError:
        raise

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": target_width, "height": 1200})
        await page.set_content(full_html)
        screenshot = await page.screenshot(full_page=True)
        await browser.close()
        return bytes(screenshot)


def _render_with_pil_fallback(block_html: str, target_width: int) -> bytes:
    plain_text = html_lib.unescape(block_html.replace("<", " <").replace(">", "> "))
    plain_text = re.sub(r"<[^>]+>", " ", plain_text)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()[:500]
    image = Image.new("RGB", (target_width, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((12, 12), plain_text[:300] or "(empty block)", fill=(0, 0, 0))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _wrap_html(block_html: str, target_width: int) -> str:
    body = block_html.strip()
    if not body:
        body = "<div></div>"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
  margin: 0;
  padding: 12px;
  font-family: Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  width: {target_width}px;
  background: #fff;
  color: #000;
}}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ccc; padding: 4px 8px; }}
</style>
</head>
<body>{body}</body>
</html>"""


def _align_sizes(
    original_bytes: bytes,
    rendered_bytes: bytes,
) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    original = Image.open(io.BytesIO(original_bytes)).convert("RGB")
    rendered = Image.open(io.BytesIO(rendered_bytes)).convert("RGB")
    rendered_resized = rendered.resize(original.size, Image.Resampling.LANCZOS)
    return np.asarray(original, dtype=np.uint8), np.asarray(rendered_resized, dtype=np.uint8)


def _array_to_png_bytes(image: NDArray[np.uint8]) -> bytes:
    output = io.BytesIO()
    Image.fromarray(image.astype(np.uint8)).save(output, format="PNG")
    return output.getvalue()


async def _ocr_consistency(rendered_bytes: bytes, original_text: str) -> float:
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("rapidocr-onnxruntime not installed; OCR consistency check skipped")
        return 0.0

    def run_ocr() -> float:
        image = Image.open(io.BytesIO(rendered_bytes)).convert("RGB")
        image_array = np.asarray(image)
        ocr = RapidOCR()
        result, _metadata = ocr(image_array)
        if not result:
            return 1.0 if original_text else 0.0
        re_ocr_text = " ".join(str(item[1]) for item in result if len(item) > 1)
        return _character_error_rate(original_text, re_ocr_text)

    try:
        return await asyncio.to_thread(run_ocr)
    except Exception as exc:
        logger.warning("rapidocr consistency check failed: %s", exc)
        return 0.0


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = " ".join(parser.parts)
    if text:
        return re.sub(r"\s+", " ", text).strip()
    return re.sub(r"<[^>]+>", " ", html).strip()


def _character_error_rate(ref: str, hyp: str) -> float:
    if not ref and not hyp:
        return 0.0
    if not ref or not hyp:
        return 1.0

    previous = list(range(len(hyp) + 1))
    for i, ref_char in enumerate(ref, start=1):
        current = [i]
        for j, hyp_char in enumerate(hyp, start=1):
            cost = 0 if ref_char == hyp_char else 1
            current.append(min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost))
        previous = current
    return min(1.0, previous[-1] / max(len(ref), 1))


def _detect_layout_boxes(img: NDArray[np.uint8]) -> list[tuple[int, int, int, int]]:
    gray = img.mean(axis=2) if img.ndim == 3 else img
    mask = gray < 245
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return []
    return [(int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)]


def _compute_box_set_iou(
    a: list[tuple[int, int, int, int]],
    b: list[tuple[int, int, int, int]],
) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return max(_box_iou(box_a, box_b) for box_a in a for box_b in b)


def _box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - inter
    return 0.0 if union == 0 else inter / union


async def _clip_similarity(original_bytes: bytes, rendered_bytes: bytes) -> float:
    def run_clip() -> float:
        try:
            import torch  # type: ignore[import-not-found]
        except ImportError:
            logger.warning("open_clip_torch dependencies not installed; CLIP check skipped")
            return 1.0

        try:
            model, preprocess, device = _get_clip()

            def encode(image_bytes: bytes) -> object:
                image = preprocess(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
                with torch.no_grad():
                    return model.encode_image(image.unsqueeze(0).to(device))

            original_embedding = encode(original_bytes)
            rendered_embedding = encode(rendered_bytes)
            cosine = torch.nn.functional.cosine_similarity(original_embedding, rendered_embedding)
            return max(0.0, min(1.0, float(cosine.item())))
        except ImportError:
            logger.warning("open_clip_torch not installed; CLIP check skipped")
            return 1.0
        except Exception as exc:
            logger.warning("CLIP similarity check failed: %s", exc)
            return 1.0

    return await asyncio.to_thread(run_clip)


def _get_clip() -> tuple[object, object, str]:
    global _clip_device, _clip_model, _clip_preprocess
    if _clip_model is None or _clip_preprocess is None or _clip_device is None:
        import open_clip  # type: ignore[import-not-found]
        import torch  # type: ignore[import-not-found]

        _clip_device = "cuda" if torch.cuda.is_available() else "cpu"
        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14",
            pretrained="openai",
            device=_clip_device,
        )
        _clip_model.eval()
    return _clip_model, _clip_preprocess, _clip_device


def _compute_ssim(a: NDArray[np.uint8], b: NDArray[np.uint8]) -> float:
    if a.shape != b.shape:
        return 0.0
    min_dim = min(a.shape[0], a.shape[1])
    if min_dim < 7:
        return 1.0 if np.array_equal(a, b) else 0.0
    score = structural_similarity(a, b, channel_axis=2, data_range=255)
    return max(0.0, min(1.0, float(score)))
