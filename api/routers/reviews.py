from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.models.parse import ParseBlockRow
from api.models.review import HumanReviewAction
from api.schemas.reviews import ReviewActionRequest, ReviewActionResponse

router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


@router.post("/actions", response_model=ReviewActionResponse)
async def submit_review_action(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ReviewActionRequest,
) -> ReviewActionResponse:
    result = await db.execute(
        select(ParseBlockRow).where(
            ParseBlockRow.workspace_id == ctx.workspace_id,
            ParseBlockRow.parse_run_id == body.parse_run_id,
            ParseBlockRow.block_id == body.block_id,
        )
    )
    parse_block = result.scalar_one_or_none()
    if parse_block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="parse block not found")

    action = HumanReviewAction(
        workspace_id=ctx.workspace_id,
        parse_block_id=parse_block.id,
        actor_id=ctx.actor_id,
        action="correction",
        payload={
            "parse_run_id": str(body.parse_run_id),
            "block_id": body.block_id,
            "corrected_text": body.corrected_text,
            "corrected_bbox": body.corrected_bbox.model_dump() if body.corrected_bbox else None,
            "mismatch_types": body.mismatch_types,
            "used_for_training_requested": body.used_for_training,
        },
    )
    parse_block.needs_review = False
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return ReviewActionResponse(action_id=action.id, status="recorded", used_for_training=False)
