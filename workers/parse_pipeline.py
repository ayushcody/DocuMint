from __future__ import annotations

import asyncio
import io
import json
import logging
import time
import traceback
from typing import NoReturn, Protocol
from uuid import UUID, uuid4

import numpy as np
from PIL import Image
from sqlalchemy import select

from api.deps import open_workspace_session
from api.models.citation import Citation
from api.models.document import Document
from api.models.parse import ParseBlockRow, ParseRun
from api.models.review import HumanReviewAction
from api.schemas.common import RunStatus
from api.services import storage
from celery_app import celery_app
from workers.assembly import ContentBlock, assemble_blocks
from workers.intake import run_intake
from workers.layout import LayoutRegion, detect_layout
from workers.specialist.mineru import parse_complex_region
from workers.specialist.olmocr import parse_degraded_or_handwritten_region
from workers.specialist.paddleocr import parse_simple_text_region
from workers.verifier import verify_parse_block

logger = logging.getLogger(__name__)


class _TaskRequest(Protocol):
    retries: int


class _RetryableTask(Protocol):
    request: _TaskRequest
    max_retries: int

    def retry(self, *, exc: BaseException, countdown: int) -> NoReturn:
        ...


@celery_app.task(bind=True, max_retries=3, name="documind.parse.run_parse_pipeline")
def run_parse_pipeline(
    self: _RetryableTask,
    parse_run_id: str,
    workspace_id: str,
) -> dict[str, object]:
    try:
        return asyncio.run(_run_parse_pipeline(UUID(parse_run_id), UUID(workspace_id)))
    except Exception as exc:
        tb = traceback.format_exc()
        asyncio.run(_mark_failed(UUID(parse_run_id), UUID(workspace_id), tb))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=min(60, 2 ** self.request.retries)) from exc
        raise


async def _run_parse_pipeline(parse_run_id: UUID, workspace_id: UUID) -> dict[str, object]:
    started = time.perf_counter()
    document_id, original_path = await _load_document_and_mark_running(parse_run_id, workspace_id)
    log_lines = [
        _log_line("parse_pipeline", "started", parse_run_id=parse_run_id, document_id=document_id),
        _log_line("storage", "loading_original", path=original_path),
    ]
    artifact_manifest: dict[str, object] = {
        "parse_run_id": str(parse_run_id),
        "workspace_id": str(workspace_id),
        "document_id": str(document_id),
        "artifacts": {
            "original": original_path,
            "renders": [],
            "crops": [],
            "ast": None,
            "logs": None,
        },
    }

    document_bytes = await storage.get_object(original_path)
    intake_result = await run_intake(
        document_bytes=document_bytes,
        document_id=str(document_id),
        workspace_id=str(workspace_id),
    )

    ast_pages: list[dict[str, object]] = []
    content_blocks: list[ContentBlock] = []
    verifier_by_block: dict[str, dict[str, object]] = {}
    crop_path_by_block: dict[str, str] = {}
    for page in intake_result["pages"]:
        page_num = int(page["page_num"])
        render_path = await storage.upload_render(
            workspace_id=workspace_id,
            document_id=document_id,
            page_num=page_num,
            image_bytes=page["render_bytes"],
        )
        _append_artifact_path(artifact_manifest, "renders", render_path)
        ast_pages.append(
            {
                "page_num": page_num,
                "dpi": page["dpi"],
                "width_px": page["width_px"],
                "height_px": page["height_px"],
                "render_path": render_path,
                "native_spans": page["native_spans"],
                "anchor_text": page["anchor_text"],
            }
        )
        log_lines.append(
            _log_line("intake", "render_uploaded", page_num=page_num, path=render_path)
        )

        regions = await detect_layout(
            page_num=page_num,
            image_bytes=page["render_bytes"],
            native_spans=page["native_spans"],
        )
        log_lines.append(
            _log_line("layout", "regions_detected", page_num=page_num, count=len(regions))
        )
        for region in regions:
            crop_path = await storage.upload_crop(
                workspace_id=workspace_id,
                document_id=document_id,
                block_id=region.block_id,
                image_bytes=region.crop_bytes,
            )
            _append_artifact_path(artifact_manifest, "crops", crop_path)
            crop_path_by_block[region.block_id] = crop_path
            block = await _parse_region(region)
            verifier = await verify_parse_block(
                original_crop=_png_to_array(region.crop_bytes),
                predicted_markdown=block.text,
                predicted_html=block.html,
            )
            verifier_by_block[block.block_id] = verifier
            content_blocks.append(
                _with_verifier_source(
                    block,
                    verifier=verifier,
                    crop_path=crop_path,
                    render_path=render_path,
                    layout_confidence=region.confidence,
                )
            )
            log_lines.append(
                _log_line(
                    "specialist",
                    "region_parsed",
                    block_id=region.block_id,
                    route=region.route,
                    crop_path=crop_path,
                )
            )

    assembled_blocks = assemble_blocks(content_blocks)
    parse_block_rows = [
        _parse_block_row(
            workspace_id=workspace_id,
            parse_run_id=parse_run_id,
            block=block,
            verifier=verifier_by_block[block.block_id],
        )
        for block in assembled_blocks
    ]
    ast_blocks = [row.ast for row in parse_block_rows]
    ast_dict: dict[str, object] = {
        "parse_run_id": str(parse_run_id),
        "workspace_id": str(workspace_id),
        "document_id": str(document_id),
        "file_hash_sha256": intake_result["file_hash_sha256"],
        "page_count": intake_result["page_count"],
        "pages": ast_pages,
        "blocks": ast_blocks,
        "next_agent": "extraction",
    }
    ast_path = await storage.upload_ast(workspace_id, document_id, parse_run_id, ast_dict)
    artifact_manifest["artifacts"]["ast"] = ast_path  # type: ignore[index]
    log_lines.append(_log_line("assembly", "ast_uploaded", path=ast_path))

    elapsed_ms = max(1, int((time.perf_counter() - started) * 1000))
    await _mark_parse_complete(
        parse_run_id=parse_run_id,
        workspace_id=workspace_id,
        document_id=document_id,
        page_count=int(intake_result["page_count"]),
        file_hash_sha256=str(intake_result["file_hash_sha256"]),
        elapsed_ms=elapsed_ms,
        parse_block_rows=parse_block_rows,
    )
    await _queue_review_actions(
        workspace_id=workspace_id,
        parse_blocks=parse_block_rows,
        verifier_by_block=verifier_by_block,
        crop_path_by_block=crop_path_by_block,
    )
    log_path = storage.log_path(workspace_id, document_id, parse_run_id)
    artifact_manifest["artifacts"]["logs"] = log_path  # type: ignore[index]
    log_lines.append(
        _log_line("artifacts", "manifest", manifest=json.dumps(artifact_manifest, sort_keys=True))
    )
    await storage.upload_log(workspace_id, document_id, parse_run_id, log_lines)
    return {
        "parse_run_id": str(parse_run_id),
        "document_id": str(document_id),
        "status": RunStatus.succeeded.value,
        "page_count": int(intake_result["page_count"]),
        "block_count": len(parse_block_rows),
        "ast_path": ast_path,
    }


async def _load_document_and_mark_running(
    parse_run_id: UUID,
    workspace_id: UUID,
) -> tuple[UUID, str]:
    async with open_workspace_session(workspace_id) as session:
        parse_run = await session.get(ParseRun, parse_run_id)
        if parse_run is None:
            raise ValueError(f"ParseRun not found for workspace: {parse_run_id}")

        result = await session.execute(
            select(Document)
            .where(Document.id == parse_run.document_id)
            .where(Document.workspace_id == workspace_id)
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ValueError(f"Document not found for parse run: {parse_run_id}")

        parse_run.status = RunStatus.running.value
        parse_run.progress = 0.05
        parse_run.error = None
        return document.id, document.storage_path


async def _mark_parse_complete(
    parse_run_id: UUID,
    workspace_id: UUID,
    document_id: UUID,
    page_count: int,
    file_hash_sha256: str,
    elapsed_ms: int,
    parse_block_rows: list[ParseBlockRow],
) -> None:
    async with open_workspace_session(workspace_id) as session:
        parse_run = await session.get(ParseRun, parse_run_id)
        document = await session.get(Document, document_id)
        if parse_run is None or document is None:
            raise ValueError(
                f"ParseRun or Document missing during intake completion: {parse_run_id}"
            )

        document.page_count = page_count
        document.file_hash_sha256 = file_hash_sha256
        parse_run.status = RunStatus.succeeded.value
        parse_run.progress = 1.0
        parse_run.agent_timings_ms = {
            **parse_run.agent_timings_ms,
            "agents_1_to_5": elapsed_ms,
        }
        parse_run.error = None
        session.add_all(parse_block_rows)
        session.add_all(_parse_level_citation_rows(workspace_id, parse_block_rows))


async def _queue_review_actions(
    workspace_id: UUID,
    parse_blocks: list[ParseBlockRow],
    verifier_by_block: dict[str, dict[str, object]],
    crop_path_by_block: dict[str, str],
) -> None:
    actions: list[HumanReviewAction] = []
    for row in parse_blocks:
        verifier = verifier_by_block[row.block_id]
        if not bool(verifier["flag_for_repair"]):
            continue
        actions.append(
            HumanReviewAction(
                id=uuid4(),
                workspace_id=workspace_id,
                parse_block_id=row.id,
                actor_id="verifier",
                action="needs_review",
                payload={
                    "block_id": row.block_id,
                    "verifier": verifier,
                    "crop_path": crop_path_by_block.get(row.block_id),
                },
            )
        )
    if not actions:
        return
    async with open_workspace_session(workspace_id) as session:
        session.add_all(actions)


def _parse_level_citation_rows(
    workspace_id: UUID,
    parse_block_rows: list[ParseBlockRow],
) -> list[Citation]:
    rows: list[Citation] = []
    for row in parse_block_rows:
        for citation in row.citations_json:
            rows.append(
                Citation(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    parse_block_id=row.id,
                    extraction_run_id=None,
                    field_name=None,
                    matching_text=str(citation.get("matching_text", "")),
                    bboxes=list(citation.get("bboxes", [])),
                    page=int(citation.get("page", row.page)),
                )
            )
    return rows


async def _mark_failed(parse_run_id: UUID, workspace_id: UUID, tb: str) -> None:
    document_id: UUID | None = None
    async with open_workspace_session(workspace_id) as session:
        parse_run = await session.get(ParseRun, parse_run_id)
        if parse_run is None:
            return
        document_id = parse_run.document_id
        parse_run.status = RunStatus.failed.value
        parse_run.error = tb[-4000:]

    if document_id is not None:
        await storage.upload_log(
            workspace_id,
            document_id,
            parse_run_id,
            [_log_line("parse_pipeline", "failed"), tb],
        )


async def _parse_region(region: LayoutRegion) -> ContentBlock:
    if region.route == "paddleocr":
        result = await parse_simple_text_region(region.crop_bytes, region.native_spans)
        text = result.text
        html = result.html
        confidence = result.confidence
        source = {
            "native_pdf": result.engine == "native_pdf_anchor",
            "ocr_engine": result.engine,
            "vlm_engine": "none",
            "layout_backend": region.layout_backend,
            "layout_backend_version": region.layout_backend_version,
        }
    elif region.route == "mineru":
        result = await parse_complex_region(region.crop_bytes, region.native_spans, region.type)
        text = result.text
        html = result.html
        confidence = result.confidence
        source = {
            "native_pdf": bool(region.native_spans),
            "ocr_engine": "native_pdf_anchor",
            "vlm_engine": result.engine,
            "warning": result.warning,
            "layout_backend": region.layout_backend,
            "layout_backend_version": region.layout_backend_version,
        }
    else:
        result = await parse_degraded_or_handwritten_region(region.crop_bytes, region.native_spans)
        text = result.text
        html = result.html
        confidence = result.confidence
        if result.stub and result.needs_review:
            confidence = min(confidence, 0.25)
            logger.warning(
                "Block %s forced to low confidence - specialist fallback: %s",
                region.block_id,
                result.stub_reason or "unknown",
            )
        source = {
            "native_pdf": bool(region.native_spans),
            "ocr_engine": result.engine,
            "vlm_engine": "olmocr",
            "prompt": result.prompt,
            "warning": result.stub_reason if result.stub else None,
            "specialist_needs_review": result.needs_review,
            "layout_backend": region.layout_backend,
            "layout_backend_version": region.layout_backend_version,
        }

    calibrated = _calibrate_confidence(confidence, region.confidence)
    citation = {
        "page": region.page,
        "matching_text": text[:120],
        "bboxes": [region.bbox],
    }
    return ContentBlock(
        block_id=region.block_id,
        page=region.page,
        type=region.type,
        bbox=region.bbox,
        text=text,
        html=html,
        confidence_raw=confidence,
        confidence_calibrated=calibrated,
        source=source,
        citations=(citation,),
    )


def _with_verifier_source(
    block: ContentBlock,
    verifier: dict[str, object],
    crop_path: str,
    render_path: str,
    layout_confidence: float,
) -> ContentBlock:
    source = {
        **block.source,
        "verifier": verifier,
        "crop_path": crop_path,
        "render_path": render_path,
        "layout_confidence": layout_confidence,
        "layout_backend": block.source.get("layout_backend"),
        "layout_backend_version": block.source.get("layout_backend_version"),
    }
    return ContentBlock(
        block_id=block.block_id,
        page=block.page,
        type=block.type,
        bbox=block.bbox,
        text=block.text,
        html=block.html,
        confidence_raw=block.confidence_raw,
        confidence_calibrated=block.confidence_calibrated,
        source=source,
        citations=block.citations,
        reading_order_rank=block.reading_order_rank,
        children=block.children,
    )


def _parse_block_row(
    workspace_id: UUID,
    parse_run_id: UUID,
    block: ContentBlock,
    verifier: dict[str, object],
) -> ParseBlockRow:
    citations = list(block.citations) or [
        {
            "page": block.page,
            "matching_text": block.text[:120],
            "bboxes": [block.bbox],
        }
    ]
    ast = {
        "block_id": block.block_id,
        "page": block.page,
        "type": block.type,
        "bbox": block.bbox,
        "reading_order_rank": block.reading_order_rank,
        "text": block.text,
        "html": block.html,
        "children": list(block.children),
        "citations": citations,
        "source": {
            "native_pdf": bool(block.source.get("native_pdf", False)),
            "ocr_engine": str(block.source.get("ocr_engine", "unknown")),
            "vlm_engine": str(block.source.get("vlm_engine", "none")),
            "verifier": verifier,
            "crop_path": block.source.get("crop_path"),
            "render_path": block.source.get("render_path"),
            "layout_confidence": block.source.get("layout_confidence"),
            "layout_backend": block.source.get("layout_backend"),
            "layout_backend_version": block.source.get("layout_backend_version"),
            "warning": block.source.get("warning"),
            "prompt": block.source.get("prompt"),
        },
        "confidence": {
            "overall": block.confidence_calibrated,
            "calibrated": block.confidence_calibrated,
            "raw": block.confidence_raw,
            "uncalibrated": block.confidence_raw,
        },
    }
    return ParseBlockRow(
        id=uuid4(),
        workspace_id=workspace_id,
        parse_run_id=parse_run_id,
        block_id=block.block_id,
        page=block.page,
        type=block.type,
        bbox=block.bbox,
        ast=ast,
        citations_json=citations,
        verifier=verifier,
        confidence=ast["confidence"],
        reading_order_rank=block.reading_order_rank,
        needs_review=bool(verifier["flag_for_repair"])
        or bool(block.source.get("specialist_needs_review", False)),
    )


def _png_to_array(png_bytes: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return np.asarray(image, dtype=np.uint8)


def _calibrate_confidence(raw: float, layout_confidence: float) -> float:
    return max(0.0, min(1.0, (raw * 0.75) + (layout_confidence * 0.25)))


def _log_line(stage: str, event: str, **payload: object) -> str:
    parts = [f"stage={stage}", f"event={event}"]
    parts.extend(f"{key}={value}" for key, value in payload.items())
    return " ".join(parts)


def _append_artifact_path(manifest: dict[str, object], key: str, path: str) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    paths = artifacts.get(key)
    if isinstance(paths, list):
        paths.append(path)
