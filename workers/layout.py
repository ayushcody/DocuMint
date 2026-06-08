from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Literal, TypedDict
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray
from PIL import Image

logger = logging.getLogger(__name__)

BlockType = Literal["paragraph", "header", "table", "figure", "equation", "footer", "handwriting"]
Route = Literal["paddleocr", "mineru", "olmocr"]
LAYOUT_BACKEND = os.getenv("DOCUMINT_LAYOUT_BACKEND", "docling")


class NativeSpan(TypedDict):
    text: str
    bbox: dict[str, float | str]
    font: str
    size: float
    anchor_prompt: str


@dataclass(frozen=True, slots=True)
class LayoutRegion:
    block_id: str
    page: int
    type: BlockType
    bbox: dict[str, float | str]
    confidence: float
    route: Route
    crop_bytes: bytes
    native_spans: list[NativeSpan]
    layout_backend: str
    layout_backend_version: str


async def detect_layout(
    page_num: int,
    image_bytes: bytes,
    native_spans: list[NativeSpan],
    source_type: Literal["native_pdf", "scan"] = "native_pdf",
) -> list[LayoutRegion]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if LAYOUT_BACKEND == "yolov9_triton":
        return await _detect_yolov9_triton(page_num, image_bytes, native_spans, source_type)
    if LAYOUT_BACKEND == "heuristic":
        logger.warning(
            "DOCUMINT_LAYOUT_BACKEND=heuristic; using heuristic layout. Not for production."
        )
        return _detect_with_heuristics(page_num, image, native_spans, source_type)
    if LAYOUT_BACKEND != "docling":
        raise RuntimeError(f"Unknown DOCUMINT_LAYOUT_BACKEND: {LAYOUT_BACKEND}")

    docling_regions = await _detect_with_docling(
        page_num,
        image_bytes,
        image,
        native_spans,
        source_type,
    )
    if docling_regions:
        return docling_regions
    if _heuristic_fallback_enabled():
        logger.warning(
            "DOCUMINT_LAYOUT_FALLBACK_HEURISTIC=true; using heuristic layout. "
            "This is not suitable for production."
        )
        return _detect_with_heuristics(page_num, image, native_spans, source_type)
    raise RuntimeError("Docling produced no layout regions and heuristic fallback is disabled")


async def _detect_yolov9_triton(
    page_num: int,
    image_bytes: bytes,
    native_spans: list[NativeSpan],
    source_type: Literal["native_pdf", "scan"],
) -> list[LayoutRegion]:
    del page_num, image_bytes, native_spans, source_type
    try:
        import tritonclient.http  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "DOCUMINT_LAYOUT_BACKEND=yolov9_triton requires tritonclient[http]. "
            "Install Triton client and provision the YOLOv9 DocLayNet model."
        ) from exc
    if not os.getenv("DOCUMINT_TRITON_URL"):
        raise RuntimeError(
            "DOCUMINT_TRITON_URL is required when DOCUMINT_LAYOUT_BACKEND=yolov9_triton."
        )
    raise NotImplementedError(
        "YOLOv9 Triton backend not yet implemented. "
        "Set DOCUMINT_LAYOUT_BACKEND=docling for CPU deployment."
    )


async def _detect_with_docling(
    page_num: int,
    image_bytes: bytes,
    image: Image.Image,
    native_spans: list[NativeSpan],
    source_type: str,
) -> list[LayoutRegion]:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        raise RuntimeError(
            "Docling is not installed. Agent 2 layout detection cannot run. "
            "Install: pip install docling"
        ) from None
    try:
        import docling

        backend_version = str(getattr(docling, "__version__", "unknown"))
    except ImportError:
        backend_version = "unknown"

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        converter = DocumentConverter()
        result = await asyncio.to_thread(converter.convert, tmp_path)
    except Exception as exc:
        logger.warning("Docling layout detection failed: %s", exc)
        return []
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass

    regions: list[LayoutRegion] = []
    width, height = image.size
    for element, _level in _iterate_docling_items(result):
        bbox = _extract_docling_bbox(element, width, height)
        if bbox is None:
            continue
        block_type = _map_docling_label(str(getattr(element, "label", "text")))
        overlapping_spans = _spans_overlapping(native_spans, bbox)
        crop_bytes = _crop_to_png(image, bbox)
        regions.append(
            LayoutRegion(
                block_id=f"blk_{uuid4().hex[:12]}",
                page=page_num,
                type=block_type,
                bbox=bbox,
                confidence=_docling_confidence(element),
                route=_route_region(block_type, bbox, source_type, overlapping_spans),
                crop_bytes=crop_bytes,
                native_spans=overlapping_spans,
                layout_backend="docling",
                layout_backend_version=backend_version,
            )
        )
    return regions


def _iterate_docling_items(result: object) -> list[tuple[object, int]]:
    document = getattr(result, "document", None)
    iterate_items = getattr(document, "iterate_items", None)
    if not callable(iterate_items):
        return []
    return list(iterate_items())


def _extract_docling_bbox(
    element: object,
    width: int,
    height: int,
) -> dict[str, float | str] | None:
    raw_bbox = getattr(element, "bbox", None)
    if raw_bbox is None:
        prov = getattr(element, "prov", None)
        if prov:
            first = prov[0]
            raw_bbox = getattr(first, "bbox", None)
    if raw_bbox is None:
        return None

    left = _first_attr(raw_bbox, ("l", "left", "x0", "x"))
    top = _first_attr(raw_bbox, ("t", "top", "y0", "y"))
    right = _first_attr(raw_bbox, ("r", "right", "x1"))
    bottom = _first_attr(raw_bbox, ("b", "bottom", "y1"))
    box_width = _first_attr(raw_bbox, ("w", "width"))
    box_height = _first_attr(raw_bbox, ("h", "height"))
    if left is None or top is None:
        return None
    if right is None and box_width is not None:
        right = left + box_width
    if bottom is None and box_height is not None:
        bottom = top + box_height
    if right is None or bottom is None:
        return None

    if max(left, top, right, bottom) <= 1.5:
        x1, y1, x2, y2 = left, top, right, bottom
    else:
        x1, y1, x2, y2 = left / width, top / height, right / width, bottom / height
    x1 = _clamp01(x1)
    y1 = _clamp01(y1)
    x2 = _clamp01(x2)
    y2 = _clamp01(y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return {
        "x": x1,
        "y": y1,
        "w": max(0.000001, x2 - x1),
        "h": max(0.000001, y2 - y1),
        "coord_space": "page_norm",
    }


def _first_attr(obj: object, names: tuple[str, ...]) -> float | None:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return float(value)
    return None


def _map_docling_label(label: str) -> BlockType:
    mapping: dict[str, BlockType] = {
        "text": "paragraph",
        "paragraph": "paragraph",
        "section_header": "header",
        "title": "header",
        "table": "table",
        "figure": "figure",
        "formula": "equation",
        "equation": "equation",
        "list_item": "paragraph",
        "page_footer": "footer",
        "page_header": "header",
        "picture": "figure",
        "caption": "paragraph",
    }
    return mapping.get(label.lower(), "paragraph")


def _docling_confidence(element: object) -> float:
    confidence = getattr(element, "confidence", None)
    if confidence is None:
        return 0.85
    return _clamp01(float(confidence))


def _detect_with_heuristics(
    page_num: int,
    image: Image.Image,
    native_spans: list[NativeSpan],
    source_type: str,
) -> list[LayoutRegion]:
    width, height = image.size
    if native_spans:
        groups = _group_spans_into_regions(native_spans)
        return [
            _region_from_span_group(page_num, index, group, image, width, height, source_type)
            for index, group in enumerate(groups)
        ]

    bbox = _foreground_bbox(np.asarray(image))
    if bbox is None:
        bbox = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "coord_space": "page_norm"}
    crop_bytes = _crop_to_png(image, bbox)
    return [
        LayoutRegion(
            block_id=f"blk_p{page_num}_scan_0",
            page=page_num,
            type="handwriting" if source_type == "scan" else "paragraph",
            bbox=bbox,
            confidence=0.45,
            route="olmocr",
            crop_bytes=crop_bytes,
            native_spans=[],
            layout_backend="heuristic",
            layout_backend_version="operator_override",
        )
    ]


def _group_spans_into_regions(spans: list[NativeSpan]) -> list[list[NativeSpan]]:
    sorted_spans = sorted(
        spans,
        key=lambda span: (float(span["bbox"]["y"]), float(span["bbox"]["x"])),
    )
    groups: list[list[NativeSpan]] = []

    for span in sorted_spans:
        if not groups:
            groups.append([span])
            continue
        previous_bbox = _union_bbox(groups[-1])
        span_bbox = span["bbox"]
        same_paragraph = (
            abs(float(span_bbox["y"]) - _bottom(previous_bbox)) < 0.035
            and abs(float(span_bbox["x"]) - float(previous_bbox["x"])) < 0.08
        )
        if same_paragraph:
            groups[-1].append(span)
        else:
            groups.append([span])
    return groups


def _region_from_span_group(
    page_num: int,
    index: int,
    spans: list[NativeSpan],
    image: Image.Image,
    width: int,
    height: int,
    source_type: str,
) -> LayoutRegion:
    bbox = _pad_bbox(_union_bbox(spans), pad_x=0.006, pad_y=0.004)
    text = " ".join(span["text"] for span in spans).strip()
    block_type = _classify_region_type(text, spans, bbox)
    crop_bytes = _crop_to_png(image, bbox)
    return LayoutRegion(
        block_id=f"blk_p{page_num}_{block_type}_{index}",
        page=page_num,
        type=block_type,
        bbox=bbox,
        confidence=_layout_confidence(spans, width, height),
        route=_route_region(block_type, bbox, source_type, spans),
        crop_bytes=crop_bytes,
        native_spans=spans,
        layout_backend="heuristic",
        layout_backend_version="operator_override",
    )


def _classify_region_type(
    text: str,
    spans: list[NativeSpan],
    bbox: dict[str, float | str],
) -> BlockType:
    lower = text.lower()
    avg_size = sum(float(span["size"]) for span in spans) / max(len(spans), 1)
    y = float(bbox["y"])
    if y > 0.92:
        return "footer"
    if avg_size >= 16 or lower.startswith(("chapter", "section", "appendix")):
        return "header"
    if any(marker in lower for marker in ("|", " total ", " amount ", " qty ", "table ")):
        return "table"
    if any(marker in lower for marker in ("=", "∑", "\\frac", " equation ")):
        return "equation"
    return "paragraph"


def _route_region(
    block_type: BlockType,
    bbox: dict[str, float | str],
    source_type: str,
    native_spans: list[NativeSpan],
) -> Route:
    if source_type == "scan" or block_type == "handwriting":
        return "olmocr"
    if block_type in {"table", "equation", "figure"} or float(bbox["w"]) > 0.75:
        return "mineru"
    if native_spans and block_type in {"paragraph", "header", "footer"}:
        return "paddleocr"
    return "olmocr"


def _heuristic_fallback_enabled() -> bool:
    return os.getenv("DOCUMINT_LAYOUT_FALLBACK_HEURISTIC", "").lower() == "true"


def _layout_confidence(spans: list[NativeSpan], width: int, height: int) -> float:
    del width, height
    if not spans:
        return 0.45
    has_text = any(span["text"].strip() for span in spans)
    return 0.88 if has_text else 0.55


def _spans_overlapping(
    spans: list[NativeSpan],
    bbox: dict[str, float | str],
) -> list[NativeSpan]:
    return [span for span in spans if _bbox_iou(span["bbox"], bbox) > 0.01]


def _union_bbox(spans: list[NativeSpan]) -> dict[str, float | str]:
    x1 = min(float(span["bbox"]["x"]) for span in spans)
    y1 = min(float(span["bbox"]["y"]) for span in spans)
    x2 = max(float(span["bbox"]["x"]) + float(span["bbox"]["w"]) for span in spans)
    y2 = max(float(span["bbox"]["y"]) + float(span["bbox"]["h"]) for span in spans)
    return {
        "x": _clamp01(x1),
        "y": _clamp01(y1),
        "w": max(0.000001, _clamp01(x2) - _clamp01(x1)),
        "h": max(0.000001, _clamp01(y2) - _clamp01(y1)),
        "coord_space": "page_norm",
    }


def _pad_bbox(
    bbox: dict[str, float | str],
    pad_x: float,
    pad_y: float,
) -> dict[str, float | str]:
    x = _clamp01(float(bbox["x"]) - pad_x)
    y = _clamp01(float(bbox["y"]) - pad_y)
    right = _clamp01(float(bbox["x"]) + float(bbox["w"]) + pad_x)
    bottom = _clamp01(float(bbox["y"]) + float(bbox["h"]) + pad_y)
    return {
        "x": x,
        "y": y,
        "w": max(0.000001, right - x),
        "h": max(0.000001, bottom - y),
        "coord_space": "page_norm",
    }


def _bottom(bbox: dict[str, float | str]) -> float:
    return float(bbox["y"]) + float(bbox["h"])


def _crop_to_png(image: Image.Image, bbox: dict[str, float | str]) -> bytes:
    width, height = image.size
    left = int(float(bbox["x"]) * width)
    top = int(float(bbox["y"]) * height)
    right = max(left + 1, int((float(bbox["x"]) + float(bbox["w"])) * width))
    bottom = max(top + 1, int((float(bbox["y"]) + float(bbox["h"])) * height))
    crop = image.crop((left, top, min(width, right), min(height, bottom)))
    output = io.BytesIO()
    crop.save(output, format="PNG")
    return output.getvalue()


def _foreground_bbox(image: NDArray[np.uint8]) -> dict[str, float | str] | None:
    gray = image.mean(axis=2)
    mask = gray < 245
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None
    height, width = gray.shape
    x1 = max(0, int(xs.min()) - 4)
    y1 = max(0, int(ys.min()) - 4)
    x2 = min(width, int(xs.max()) + 5)
    y2 = min(height, int(ys.max()) + 5)
    return {
        "x": x1 / width,
        "y": y1 / height,
        "w": max(0.000001, (x2 - x1) / width),
        "h": max(0.000001, (y2 - y1) / height),
        "coord_space": "page_norm",
    }


def _bbox_iou(left: dict[str, float | str], right: dict[str, float | str]) -> float:
    lx1 = float(left["x"])
    ly1 = float(left["y"])
    lx2 = lx1 + float(left["w"])
    ly2 = ly1 + float(left["h"])
    rx1 = float(right["x"])
    ry1 = float(right["y"])
    rx2 = rx1 + float(right["w"])
    ry2 = ry1 + float(right["h"])
    ix1 = max(lx1, rx1)
    iy1 = max(ly1, ry1)
    ix2 = min(lx2, rx2)
    iy2 = min(ly2, ry2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    left_area = max(0.0, (lx2 - lx1) * (ly2 - ly1))
    right_area = max(0.0, (rx2 - rx1) * (ry2 - ry1))
    union = left_area + right_area - inter
    return inter / union if union else 0.0


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
