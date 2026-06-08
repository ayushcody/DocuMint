from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

from workers.layout import NativeSpan

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WordBox:
    text: str
    bbox: dict[str, float | str]
    confidence: float


@dataclass(frozen=True, slots=True)
class PaddleOCRResult:
    text: str
    html: str
    word_boxes: list[WordBox]
    confidence: float
    engine: str


async def parse_simple_text_region(
    crop_bytes: bytes,
    native_spans: list[NativeSpan],
) -> PaddleOCRResult:
    anchored_boxes = [
        WordBox(text=span["text"], bbox=span["bbox"], confidence=0.98)
        for span in native_spans
        if span["text"].strip()
    ]
    if anchored_boxes:
        text = " ".join(box.text for box in anchored_boxes).strip()
        return PaddleOCRResult(
            text=text,
            html=f"<p>{_escape_html(text)}</p>",
            word_boxes=anchored_boxes,
            confidence=0.96,
            engine="native_pdf_anchor",
        )

    ocr_result = await _try_paddleocr(crop_bytes)
    if ocr_result is not None:
        return ocr_result

    return PaddleOCRResult(
        text="",
        html="<p></p>",
        word_boxes=[],
        confidence=0.20,
        engine="paddleocr_unavailable",
    )


async def _try_paddleocr(crop_bytes: bytes) -> PaddleOCRResult | None:
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("PaddleOCR not installed; falling back to native spans")
        return None

    try:
        image = Image.open(io.BytesIO(crop_bytes)).convert("RGB")
        image_array = np.asarray(image)
        try:
            ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        except TypeError:
            ocr = PaddleOCR(use_angle_cls=True, lang="en")
        result = await asyncio.to_thread(ocr.ocr, image_array, cls=True)
    except Exception as exc:
        logger.error("PaddleOCR failed: %s", exc)
        return None

    if not result or not result[0]:
        return None

    height, width = image_array.shape[:2]
    word_boxes: list[WordBox] = []
    full_text_parts: list[str] = []
    confidences: list[float] = []
    for line in result[0]:
        box, (text, confidence) = line
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        normalized_bbox = {
            "x": _clamp01(min(xs) / width),
            "y": _clamp01(min(ys) / height),
            "w": _clamp01((max(xs) - min(xs)) / width),
            "h": _clamp01((max(ys) - min(ys)) / height),
            "coord_space": "region_norm",
        }
        conf = float(confidence)
        word_boxes.append(WordBox(text=str(text), bbox=normalized_bbox, confidence=round(conf, 4)))
        full_text_parts.append(str(text))
        confidences.append(conf)

    text = " ".join(full_text_parts).strip()
    if not text:
        return None
    mean_confidence = sum(confidences) / max(len(confidences), 1)
    return PaddleOCRResult(
        text=text,
        html=f"<p>{_escape_html(text)}</p>",
        word_boxes=word_boxes,
        confidence=round(mean_confidence, 4),
        engine="paddleocr",
    )


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
