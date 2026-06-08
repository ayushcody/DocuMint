from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.models.parse import ParseBlockRow, ParseRun
from api.models.split_classify import ClassificationRun
from api.schemas.classify import ClassifyRunRequest, ClassifyRunResponse
from workers.classify_worker import classify_document

router = APIRouter(prefix="/v1/classify", tags=["classify"])


@router.post("/runs", response_model=ClassifyRunResponse)
async def create_classify_run(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ClassifyRunRequest,
) -> ClassifyRunResponse:
    try:
        await _require_parse_run(ctx, db, body.parse_run_id)
        blocks = await _load_parse_blocks(ctx, db, body.parse_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    taxonomy = [
        item if isinstance(item, str) else item.model_dump(mode="json")
        for item in body.taxonomy
    ]
    classifications = await classify_document(blocks, taxonomy)
    page_labels = {
        int(item["page_num"]): str(item["label"])
        for item in classifications
    }
    run_id = uuid4()
    db.add(
        ClassificationRun(
            id=run_id,
            workspace_id=ctx.workspace_id,
            parse_run_id=body.parse_run_id,
            status="succeeded",
            taxonomy=[
                item if isinstance(item, str) else str(item.get("label", ""))
                for item in taxonomy
            ],
            page_labels={str(page): label for page, label in page_labels.items()},
            scores={
                f"{item['page_num']}:{label}": float(score)
                for item in classifications
                for label, score in item.get("scores", {}).items()
                if isinstance(item.get("scores", {}), dict)
            },
        )
    )
    await db.commit()
    return ClassifyRunResponse(
        run_id=run_id,
        page_labels=page_labels,
        classifications=classifications,
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
