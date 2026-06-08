from __future__ import annotations

from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext
from api.models.citation import Citation
from api.models.extraction import ExtractionRun, ExtractionSchema
from api.models.parse import ParseBlockRow, ParseRun
from api.schemas.extract import (
    ExtractionResultResponse,
    ExtractionRunResponse,
    ExtractionSchemaCreateResponse,
    FieldMetadata,
)


async def create_extraction_schema(
    ctx: WorkspaceContext,
    db: AsyncSession,
    name: str,
    json_schema: dict[str, object],
) -> ExtractionSchemaCreateResponse:
    schema_id = uuid4()
    schema = ExtractionSchema(
        id=schema_id,
        workspace_id=ctx.workspace_id,
        name=name,
        json_schema=json_schema,
    )
    db.add(schema)
    await db.commit()
    return ExtractionSchemaCreateResponse(schema_id=schema_id, name=name)


async def run_extraction(
    ctx: WorkspaceContext,
    db: AsyncSession,
    parse_run_id: UUID,
    schema_id: UUID,
) -> ExtractionRunResponse:
    parse_run = await _require_parse_run(ctx, db, parse_run_id)
    if parse_run.status != "succeeded":
        raise ValueError(f"parse_run status is '{parse_run.status}' - must be 'succeeded'")
    await _require_schema(ctx, db, schema_id)

    extraction_run_id = uuid4()
    extraction_run = ExtractionRun(
        id=extraction_run_id,
        workspace_id=ctx.workspace_id,
        parse_run_id=parse_run_id,
        schema_id=schema_id,
        data={},
        field_metadata={},
        status="queued",
    )
    db.add(extraction_run)
    await db.commit()

    from workers.extraction_pipeline import run_extraction_task

    run_extraction_task.apply_async(
        args=[str(extraction_run_id), str(ctx.workspace_id)],
        task_id=str(extraction_run_id),
    )
    return ExtractionRunResponse(run_id=extraction_run_id, status="queued")


def _extraction_citation_rows(
    workspace_id: UUID,
    extraction_run_id: UUID,
    metadata: dict[str, dict[str, object]],
) -> list[Citation]:
    rows: list[Citation] = []
    for field_name, field_metadata in metadata.items():
        if field_name.startswith("_"):
            continue
        citations = field_metadata.get("citations", [])
        if not isinstance(citations, list):
            continue
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            rows.append(
                Citation(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    parse_block_id=None,
                    extraction_run_id=extraction_run_id,
                    field_name=field_name,
                    matching_text=str(citation.get("matching_text", "")),
                    bboxes=list(citation.get("bboxes", [])),
                    page=int(citation.get("page", 0)),
                )
            )
    return rows


async def get_extraction_run(
    ctx: WorkspaceContext,
    db: AsyncSession,
    run_id: UUID,
) -> ExtractionResultResponse:
    result = await db.execute(
        select(ExtractionRun)
        .where(ExtractionRun.id == run_id)
        .where(ExtractionRun.workspace_id == ctx.workspace_id)
    )
    extraction_run = result.scalar_one_or_none()
    if extraction_run is None:
        raise KeyError(f"extraction_run_id not found in workspace: {run_id}")

    public_metadata = {
        field: value
        for field, value in extraction_run.field_metadata.items()
        if not field.startswith("_")
    }
    error_metadata = extraction_run.field_metadata.get("_error", {})
    error = str(error_metadata.get("message")) if isinstance(error_metadata, dict) else None
    status: Literal["queued", "running", "complete", "failed"]
    if extraction_run.status == "succeeded":
        status = "complete"
    elif extraction_run.status in {"queued", "running", "complete", "failed"}:
        status = cast(Literal["queued", "running", "complete", "failed"], extraction_run.status)
    else:
        status = "failed"
    return ExtractionResultResponse(
        run_id=extraction_run.id,
        status=status,
        data=extraction_run.data if status == "complete" else None,
        field_metadata={
            field: FieldMetadata.model_validate(value)
            for field, value in public_metadata.items()
        }
        if status == "complete"
        else None,
        cost_credits=0.0,
        error=error if status == "failed" else None,
    )


async def _require_schema(
    ctx: WorkspaceContext,
    db: AsyncSession,
    schema_id: UUID,
) -> ExtractionSchema:
    result = await db.execute(
        select(ExtractionSchema)
        .where(ExtractionSchema.id == schema_id)
        .where(ExtractionSchema.workspace_id == ctx.workspace_id)
    )
    schema = result.scalar_one_or_none()
    if schema is None:
        raise KeyError(f"schema_id not found in workspace: {schema_id}")
    return schema


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


async def _load_parse_block_asts(
    ctx: WorkspaceContext,
    db: AsyncSession,
    parse_run_id: UUID,
) -> list[dict[str, object]]:
    result = await db.execute(
        select(ParseBlockRow)
        .where(ParseBlockRow.parse_run_id == parse_run_id)
        .where(ParseBlockRow.workspace_id == ctx.workspace_id)
        .order_by(ParseBlockRow.page, ParseBlockRow.reading_order_rank)
    )
    rows = list(result.scalars())
    if not rows:
        raise KeyError(f"parse_run_id has no parse blocks: {parse_run_id}")
    return [row.ast for row in rows]
