from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.ml_preflight import PROFILE, rag_enabled
from api.schemas.index import (
    CollectionCreateRequest,
    CollectionCreateResponse,
    CollectionSyncRequest,
    CollectionSyncResponse,
)
from api.services import index_service

router = APIRouter(prefix="/v1", tags=["index"])


@router.post("/index/collections", response_model=CollectionCreateResponse)
async def create_collection(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: CollectionCreateRequest,
) -> CollectionCreateResponse:
    return await index_service.create_collection(
        ctx,
        db,
        body.name,
        body.enable_binary_quantization,
    )


@router.post("/index/collections/{collection_id}/sync", response_model=CollectionSyncResponse)
async def sync_collection(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    collection_id: UUID,
    body: CollectionSyncRequest,
) -> CollectionSyncResponse:
    if not rag_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"RAG indexing is not enabled in profile '{PROFILE}'. "
                "Set DOCUMINT_PROFILE=full to enable Agent 7."
            ),
        )
    try:
        return await index_service.sync_collection(
            ctx,
            db,
            collection_id,
            body.resolved_parse_run_ids(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
