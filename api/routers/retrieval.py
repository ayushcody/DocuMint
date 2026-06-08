from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.ml_preflight import PROFILE, rag_enabled
from api.schemas.index import RetrievalQueryRequest, RetrievalQueryResponse
from api.services import index_service

router = APIRouter(prefix="/v1/retrieval", tags=["retrieval"])


@router.post("/query", response_model=RetrievalQueryResponse)
async def retrieval_query(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: RetrievalQueryRequest,
) -> RetrievalQueryResponse:
    if not rag_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"RAG retrieval is not enabled in profile '{PROFILE}'. "
                "Set DOCUMINT_PROFILE=full to enable Agent 7."
            ),
        )
    try:
        return await index_service.query_collection(
            ctx,
            db,
            body.collection_id,
            body.query,
            body.limit,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
