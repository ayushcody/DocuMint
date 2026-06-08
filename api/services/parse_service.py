from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from celery.result import AsyncResult
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext
from api.models.document import Document
from api.models.parse import ParseBlockRow, ParseRun
from api.schemas.common import ParseBlock, RunStatus
from api.schemas.parse import (
    FileUploadResponse,
    ParseBlocksResponse,
    ParseConfig,
    ParseRunCreateResponse,
    ParseRunStatusResponse,
)
from api.services import storage
from celery_app import celery_app
from workers.parse_pipeline import run_parse_pipeline


async def store_uploaded_file(
    ctx: WorkspaceContext,
    db: AsyncSession,
    upload: UploadFile,
) -> FileUploadResponse:
    content = await upload.read()
    document_id = uuid4()
    filename = upload.filename or "document.pdf"
    content_type = upload.content_type or "application/pdf"
    sha256 = hashlib.sha256(content).hexdigest()
    object_path = await storage.upload_original(
        workspace_id=ctx.workspace_id,
        document_id=document_id,
        file_bytes=content,
        filename=filename,
    )

    document = Document(
        id=document_id,
        workspace_id=ctx.workspace_id,
        filename=filename,
        file_hash_sha256=sha256,
        storage_path=object_path,
        content_type=content_type,
        byte_size=len(content),
        page_count=0,
    )
    db.add(document)
    await db.commit()

    return FileUploadResponse(file_id=document_id, object_path=object_path, sha256=sha256)


async def start_parse_run(
    ctx: WorkspaceContext,
    db: AsyncSession,
    file_id: UUID,
    config: ParseConfig,
) -> ParseRunCreateResponse:
    document = await _require_document(ctx, db, file_id)
    parse_run_id = uuid4()
    parse_run = ParseRun(
        id=parse_run_id,
        workspace_id=ctx.workspace_id,
        document_id=document.id,
        status=RunStatus.queued.value,
        progress=0.0,
        cost_credits=0.0,
        config_json=config.model_dump(mode="json"),
        agent_timings_ms={},
        error=None,
    )
    db.add(parse_run)
    await db.commit()

    run_parse_pipeline.apply_async(
        args=[str(parse_run_id), str(ctx.workspace_id)],
        task_id=str(parse_run_id),
    )
    return ParseRunCreateResponse(job_id=parse_run_id, status=RunStatus.queued)


async def get_parse_run_status(
    ctx: WorkspaceContext,
    db: AsyncSession,
    run_id: UUID,
) -> ParseRunStatusResponse:
    parse_run = await _require_parse_run(ctx, db, run_id)
    celery_result = AsyncResult(str(run_id), app=celery_app)
    status_value = _status_from_db_and_celery(parse_run.status, celery_result.state)

    return ParseRunStatusResponse(
        id=parse_run.id,
        status=status_value,
        progress=max(0.0, min(1.0, float(parse_run.progress))),
        cost_credits=max(0.0, float(parse_run.cost_credits)),
        agent_timings_ms=parse_run.agent_timings_ms,
        error=parse_run.error,
    )


async def get_parse_blocks(
    ctx: WorkspaceContext,
    db: AsyncSession,
    run_id: UUID,
) -> ParseBlocksResponse:
    parse_run = await _require_parse_run(ctx, db, run_id)
    document = await _require_document(ctx, db, parse_run.document_id)
    status_value = RunStatus(parse_run.status)
    if status_value not in {RunStatus.intake_complete, RunStatus.succeeded}:
        return ParseBlocksResponse(
            run_id=run_id,
            status=status_value,
            pages_done=0,
            pages_total=document.page_count,
            blocks=[],
        )

    result = await db.execute(
        select(ParseBlockRow)
        .where(ParseBlockRow.workspace_id == ctx.workspace_id)
        .where(ParseBlockRow.parse_run_id == run_id)
        .order_by(ParseBlockRow.page, ParseBlockRow.reading_order_rank, ParseBlockRow.block_id)
    )
    blocks = [ParseBlock.model_validate(row.ast) for row in result.scalars()]
    return ParseBlocksResponse(
        run_id=run_id,
        status=status_value,
        pages_done=document.page_count,
        pages_total=document.page_count,
        blocks=blocks,
    )


async def _require_document(
    ctx: WorkspaceContext,
    db: AsyncSession,
    document_id: UUID,
) -> Document:
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.workspace_id == ctx.workspace_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise KeyError(f"file_id not found in workspace: {document_id}")
    return document


async def _require_parse_run(
    ctx: WorkspaceContext,
    db: AsyncSession,
    parse_run_id: UUID,
) -> ParseRun:
    result = await db.execute(
        select(ParseRun)
        .where(ParseRun.id == parse_run_id)
        .where(ParseRun.workspace_id == ctx.workspace_id)
    )
    parse_run = result.scalar_one_or_none()
    if parse_run is None:
        raise KeyError(f"parse_run_id not found in workspace: {parse_run_id}")
    return parse_run


def _status_from_db_and_celery(db_status: str, celery_state: str) -> RunStatus:
    if db_status in {
        RunStatus.intake_complete.value,
        RunStatus.succeeded.value,
    }:
        return RunStatus(db_status)
    if db_status == RunStatus.failed.value:
        return RunStatus.failed
    if db_status == RunStatus.cancelled.value:
        return RunStatus.cancelled
    if celery_state in {"PENDING", "RECEIVED", "RETRY"}:
        return RunStatus.queued
    if celery_state == "STARTED":
        return RunStatus.running
    if celery_state == "FAILURE":
        return RunStatus.failed
    if celery_state == "SUCCESS" and db_status in {RunStatus.queued.value, RunStatus.running.value}:
        return RunStatus.running
    return RunStatus(db_status)
