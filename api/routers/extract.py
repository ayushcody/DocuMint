from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.schemas.extract import (
    ExtractionResultResponse,
    ExtractionRunRequest,
    ExtractionRunResponse,
    ExtractionSchemaCreateRequest,
    ExtractionSchemaCreateResponse,
)
from api.services import extract_service

router = APIRouter(prefix="/v1/extract", tags=["extract"])


@router.post("/schemas", response_model=ExtractionSchemaCreateResponse)
async def create_schema(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ExtractionSchemaCreateRequest,
) -> ExtractionSchemaCreateResponse:
    return await extract_service.create_extraction_schema(ctx, db, body.name, body.json_schema)


@router.post("/runs", response_model=ExtractionRunResponse)
async def create_extraction_run(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ExtractionRunRequest,
) -> ExtractionRunResponse:
    try:
        return await extract_service.run_extraction(ctx, db, body.parse_run_id, body.schema_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=ExtractionResultResponse)
async def get_extraction_run(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    run_id: UUID,
) -> ExtractionResultResponse:
    try:
        return await extract_service.get_extraction_run(ctx, db, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
