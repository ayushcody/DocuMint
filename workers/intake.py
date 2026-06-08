from __future__ import annotations

import asyncio
import hashlib
import io
from dataclasses import dataclass
from typing import TypedDict

DPI = 300


class NativeSpanDict(TypedDict):
    text: str
    bbox: dict[str, float | str]
    font: str
    size: float
    anchor_prompt: str


class IntakePageDict(TypedDict):
    page_num: int
    width_px: int
    height_px: int
    dpi: int
    render_bytes: bytes
    native_spans: list[NativeSpanDict]
    anchor_text: str


class IntakeResult(TypedDict):
    file_hash_sha256: str
    page_count: int
    pages: list[IntakePageDict]


@dataclass(frozen=True, slots=True)
class NativeTextSpan:
    text: str
    bbox: dict[str, float | str]
    font: str
    size: float

    @property
    def anchor_prompt(self) -> str:
        x = float(self.bbox["x"])
        y = float(self.bbox["y"])
        w = float(self.bbox["w"])
        h = float(self.bbox["h"])
        escaped_text = self.text.replace("'", "\\'")
        return f"Native text at bbox [{x:.6f},{y:.6f},{w:.6f},{h:.6f}]: '{escaped_text}'"

    def as_dict(self) -> NativeSpanDict:
        return {
            "text": self.text,
            "bbox": self.bbox,
            "font": self.font,
            "size": self.size,
            "anchor_prompt": self.anchor_prompt,
        }


@dataclass(frozen=True, slots=True)
class IntakePage:
    page_num: int
    width_px: int
    height_px: int
    render_bytes: bytes
    native_spans: list[NativeTextSpan]

    @property
    def anchor_text(self) -> str:
        return "\n".join(span.anchor_prompt for span in self.native_spans if span.text.strip())

    def as_dict(self) -> IntakePageDict:
        return {
            "page_num": self.page_num,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "dpi": DPI,
            "render_bytes": self.render_bytes,
            "native_spans": [span.as_dict() for span in self.native_spans],
            "anchor_text": self.anchor_text,
        }


async def run_intake(
    document_bytes: bytes,
    document_id: str,
    workspace_id: str,
) -> IntakeResult:
    """
    Agent 1: document anchoring, hashing, and 300 DPI rasterisation.

    PyMuPDF is synchronous, so all PDF parsing and rasterisation runs in a worker
    thread. The caller owns MinIO writes so this function is easy to test and
    does not mix parsing with storage side effects.
    """
    del document_id, workspace_id
    file_hash, pages = await asyncio.to_thread(_extract_document_pages, document_bytes)
    return {
        "file_hash_sha256": file_hash,
        "page_count": len(pages),
        "pages": [page.as_dict() for page in pages],
    }


def _extract_document_pages(document_bytes: bytes) -> tuple[str, list[IntakePage]]:
    try:
        return _extract_pdf_pages(document_bytes)
    except ValueError:
        try:
            return _extract_image_page(document_bytes)
        except ValueError as image_error:
            raise ValueError(
                "Unsupported document bytes. Intake accepts PDF, PNG, JPEG, TIFF, BMP, "
                "and WebP inputs."
            ) from image_error


def _extract_pdf_pages(document_bytes: bytes) -> tuple[str, list[IntakePage]]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PyMuPDF is required for document intake. Install the backend deps."
        ) from exc

    file_hash = hashlib.sha256(document_bytes).hexdigest()
    try:
        doc = fitz.open(stream=document_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("Input is not a readable PDF") from exc

    pages: list[IntakePage] = []
    for page_num, page in enumerate(doc):
        page_rect = page.rect
        page_width = max(float(page_rect.width), 1.0)
        page_height = max(float(page_rect.height), 1.0)
        native_spans: list[NativeTextSpan] = []

        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = str(span.get("text", ""))
                    if not text.strip():
                        continue
                    bbox = _normalize_span_bbox(
                        span.get("bbox", (0, 0, 0, 0)),
                        page_width,
                        page_height,
                    )
                    native_spans.append(
                        NativeTextSpan(
                            text=text,
                            bbox=bbox,
                            font=str(span.get("font", "")),
                            size=float(span.get("size", 0.0)),
                        )
                    )

        matrix = fitz.Matrix(DPI / 72, DPI / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pages.append(
            IntakePage(
                page_num=page_num,
                width_px=int(pix.width),
                height_px=int(pix.height),
                render_bytes=pix.tobytes("png"),
                native_spans=native_spans,
            )
        )

    doc.close()
    return file_hash, pages


def _extract_image_page(document_bytes: bytes) -> tuple[str, list[IntakePage]]:
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required for image intake.") from exc

    try:
        with Image.open(io.BytesIO(document_bytes)) as image:
            normalized = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise ValueError("Input is not a readable image") from exc

    buffer = io.BytesIO()
    normalized.save(buffer, format="PNG", dpi=(DPI, DPI))
    file_hash = hashlib.sha256(document_bytes).hexdigest()
    page = IntakePage(
        page_num=0,
        width_px=normalized.width,
        height_px=normalized.height,
        render_bytes=buffer.getvalue(),
        native_spans=[],
    )
    return file_hash, [page]


def _normalize_span_bbox(
    bbox: object,
    page_width: float,
    page_height: float,
) -> dict[str, float | str]:
    try:
        x0, y0, x1, y1 = (float(v) for v in bbox)  # type: ignore[union-attr]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid PyMuPDF span bbox: {bbox!r}") from exc

    x = _clamp01(x0 / page_width)
    y = _clamp01(y0 / page_height)
    w = _clamp01(max(0.0, x1 - x0) / page_width)
    h = _clamp01(max(0.0, y1 - y0) / page_height)
    return {
        "x": x,
        "y": y,
        "w": max(w, 0.000001),
        "h": max(h, 0.000001),
        "coord_space": "page_norm",
    }


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
