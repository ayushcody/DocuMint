from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.models.parse import ParseBlockRow, ParseRun
from api.models.split_classify import SplitRun
from api.schemas.split import SplitRunRequest, SplitRunResponse, SplitSegment
from workers.split_worker import split_document

router = APIRouter(prefix="/v1/split", tags=["split"])


@router.post("/runs", response_model=SplitRunResponse)
async def create_split_run(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: SplitRunRequest,
) -> SplitRunResponse:
    try:
        await _require_parse_run(ctx, db, body.parse_run_id)
        blocks = await _load_parse_blocks(ctx, db, body.parse_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    segments = await split_document(blocks, body.config)
    run_id = uuid4()
    db.add(
        SplitRun(
            id=run_id,
            workspace_id=ctx.workspace_id,
            parse_run_id=body.parse_run_id,
            status="succeeded",
            segments=segments,
        )
    )
    await db.commit()
    return SplitRunResponse(
        run_id=run_id,
        segments=[SplitSegment.model_validate(segment) for segment in segments],
    )


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


async def _load_parse_blocks(
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
