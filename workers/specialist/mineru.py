from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import re
import tempfile
from dataclasses import dataclass

import httpx
from PIL import Image

from workers.layout import NativeSpan

logger = logging.getLogger(__name__)

MINERU_ENDPOINT = os.getenv("DOCUMINT_MINERU_ENDPOINT", "")
MINERU_MODEL = os.getenv("DOCUMINT_MINERU_MODEL", "mineru-2.5-pro")
USE_DOCLING_FALLBACK = os.getenv("DOCUMINT_MINERU_USE_DOCLING", "true").lower() == "true"


@dataclass(frozen=True, slots=True)
class TableResult:
    html: str
    teds_estimate: float


@dataclass(frozen=True, slots=True)
class MinerUResult:
    text: str
    html: str
    tables: list[TableResult]
    confidence: float
    engine: str
    warning: str | None
    teds_estimate: float
    stub: bool
    stub_reason: str | None = None


async def parse_complex_region(
    crop_bytes: bytes,
    native_spans: list[NativeSpan],
    block_type: str,
) -> MinerUResult:
    if MINERU_ENDPOINT:
        endpoint_result = await _call_mineru_endpoint(crop_bytes, native_spans, block_type)
        if endpoint_result is not None:
            return endpoint_result

    if USE_DOCLING_FALLBACK:
        docling_result = await _docling_table_extract(crop_bytes)
        if docling_result is not None:
            return docling_result

    marker_result = await _marker_extract(crop_bytes, block_type)
    if marker_result is not None:
        return marker_result

    logger.error(
        "MinerU: all backends failed; returning native spans only. "
        "TEDS will be penalized to 0.0."
    )
    text = " ".join(span["text"] for span in native_spans if span["text"].strip()).strip()
    html = (
        _native_text_to_table_html(text)
        if block_type == "table"
        else f"<div>{_escape_html(text)}</div>"
    )
    tables = [TableResult(html=html, teds_estimate=0.0)] if block_type == "table" else []
    return MinerUResult(
        text=text,
        html=html,
        tables=tables,
        confidence=0.25,
        engine="native_spans_only",
        warning="MinerU fallback exhausted - native spans only",
        teds_estimate=0.0,
        stub=True,
        stub_reason="all_backends_failed",
    )


async def _call_mineru_endpoint(
    crop_bytes: bytes,
    native_spans: list[NativeSpan],
    region_type: str,
) -> MinerUResult | None:
    try:
        image_b64 = base64.b64encode(crop_bytes).decode("ascii")
        anchor_text = "\n".join(
            f"Native text at {span.get('bbox', '')}: '{span.get('text', '')}'"
            for span in native_spans
            if span.get("text", "").strip()
        )
        prompt = (
            f"Native PDF text in this region:\n{anchor_text}\n\n"
            f"Region type: {region_type}\n"
            "Extract the complete structured content. For tables, output valid HTML table. "
            "For formulas, output LaTeX. Preserve all values exactly."
        )
        payload = {
            "model": MINERU_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 2048,
            "temperature": 0.0,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{MINERU_ENDPOINT.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {os.getenv('DOCUMINT_MINERU_API_KEY', 'none')}"
                },
            )
            response.raise_for_status()
            content = str(response.json()["choices"][0]["message"]["content"])
    except Exception as exc:
        logger.warning("MinerU endpoint failed: %s", exc)
        return None

    tables = _extract_html_tables(content, teds_estimate=0.92)
    html = content if "<table" in content.lower() else f"<p>{_escape_html(content)}</p>"
    return MinerUResult(
        text=content,
        html=html,
        tables=tables,
        confidence=0.90,
        engine="mineru_2.5_pro",
        warning=None,
        teds_estimate=0.92 if tables else 0.80,
        stub=False,
    )


async def _docling_table_extract(crop_bytes: bytes) -> MinerUResult | None:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Docling not installed; skipping Docling CPU table extraction")
        return None

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(crop_bytes)
            tmp_path = tmp.name

        def convert() -> tuple[str, list[TableResult]]:
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            document = result.document
            raw_tables = getattr(document, "tables", []) or []
            tables: list[TableResult] = []
            for table in raw_tables:
                export_to_html = getattr(table, "export_to_html", None)
                if callable(export_to_html):
                    tables.append(TableResult(html=str(export_to_html()), teds_estimate=0.82))
            export_to_markdown = getattr(document, "export_to_markdown", None)
            text = str(export_to_markdown()) if callable(export_to_markdown) else ""
            return text, tables

        text, tables = await asyncio.to_thread(convert)
    except Exception as exc:
        logger.warning("Docling table extraction failed: %s", exc)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass

    html = "\n".join(table.html for table in tables) if tables else f"<p>{_escape_html(text)}</p>"
    return MinerUResult(
        text=text,
        html=html,
        tables=tables,
        confidence=0.78 if tables else 0.60,
        engine="docling_cpu",
        warning=None if tables else "Docling CPU extraction produced no tables",
        teds_estimate=0.82 if tables else 0.60,
        stub=False,
    )


async def _marker_extract(crop_bytes: bytes, block_type: str) -> MinerUResult | None:
    try:
        from marker.converters.pdf import PdfConverter  # type: ignore[import-not-found]
        from marker.models import create_model_dict  # type: ignore[import-not-found]
        from marker.output import text_from_rendered  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("marker-pdf not installed; skipping marker fallback")
        return None

    tmp_path = ""
    try:
        image = Image.open(io.BytesIO(crop_bytes)).convert("RGB")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        await asyncio.to_thread(image.save, tmp_path, "PDF", resolution=300.0)
        models = await asyncio.to_thread(create_model_dict)
        converter = PdfConverter(artifact_dict=models)
        rendered = await asyncio.to_thread(converter, tmp_path)
        rendered_text = await asyncio.to_thread(text_from_rendered, rendered)
        markdown = _rendered_text_to_markdown(rendered_text, rendered)
        html = str(getattr(rendered, "html", "") or "") or _markdown_tables_to_html(markdown)
    except Exception as exc:
        logger.warning("marker-pdf fallback failed: %s", exc)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass

    tables = (
        [TableResult(html=html, teds_estimate=0.45)]
        if block_type == "table" and "<table" in html.lower()
        else []
    )
    return MinerUResult(
        text=markdown,
        html=html,
        tables=tables,
        confidence=0.62 if markdown else 0.25,
        engine="marker_pdf_cpu_fallback",
        warning="MinerU fallback - marker-pdf CPU backend, not MinerU2.5-Pro",
        teds_estimate=0.45 if tables else 0.30,
        stub=True,
        stub_reason="marker_pdf_cpu_fallback",
    )


def _extract_html_tables(html_content: str, teds_estimate: float) -> list[TableResult]:
    tables = re.findall(r"<table.*?>.*?</table>", html_content, re.DOTALL | re.IGNORECASE)
    return [TableResult(html=table, teds_estimate=teds_estimate) for table in tables]


def _native_text_to_table_html(text: str) -> str:
    tokens = [token for token in text.split() if token]
    if not tokens:
        return "<table></table>"
    cells = "".join(f"<td>{_escape_html(token)}</td>" for token in tokens)
    return f"<table><tbody><tr>{cells}</tr></tbody></table>"


def _rendered_text_to_markdown(rendered_text: object, rendered: object) -> str:
    if isinstance(rendered_text, tuple) and rendered_text:
        return str(rendered_text[0] or "")
    if isinstance(rendered_text, str):
        return rendered_text
    return str(getattr(rendered, "markdown", "") or "")


def _markdown_tables_to_html(markdown: str) -> str:
    html_parts: list[str] = []
    table_rows: list[list[str]] = []
    in_table = False

    for line in markdown.splitlines():
        if "|" in line and line.strip().startswith("|"):
            in_table = True
            table_rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
            continue
        if in_table:
            html_parts.append(_rows_to_html_table(table_rows))
            table_rows = []
            in_table = False
        if line.strip():
            html_parts.append(f"<p>{_escape_html(line.strip())}</p>")

    if in_table:
        html_parts.append(_rows_to_html_table(table_rows))
    return "\n".join(part for part in html_parts if part)


def _rows_to_html_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    html_rows: list[str] = []
    for index, row in enumerate(rows):
        if index == 1 and all(set(cell) <= set("-: ") for cell in row):
            continue
        tag = "th" if index == 0 else "td"
        html_rows.append(
            "<tr>" + "".join(f"<{tag}>{_escape_html(cell)}</{tag}>" for cell in row) + "</tr>"
        )
    return "<table>" + "".join(html_rows) + "</table>"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
