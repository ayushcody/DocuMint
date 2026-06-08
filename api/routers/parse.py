from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.schemas.parse import (
    FileUploadResponse,
    ParseBlocksResponse,
    ParseRunCreateResponse,
    ParseRunRequest,
    ParseRunStatusResponse,
)
from api.services import parse_service

router = APIRouter(prefix="/v1", tags=["parse"])


@router.post("/files", response_model=FileUploadResponse)
async def upload_file(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> FileUploadResponse:
    return await parse_service.store_uploaded_file(ctx, db, file)


@router.post("/parse/runs", response_model=ParseRunCreateResponse)
async def create_parse_run(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ParseRunRequest,
) -> ParseRunCreateResponse:
    try:
        return await parse_service.start_parse_run(ctx, db, body.file_id, body.config)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/parse/runs/{run_id}", response_model=ParseRunStatusResponse)
async def get_parse_run(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    run_id: UUID,
) -> ParseRunStatusResponse:
    try:
        return await parse_service.get_parse_run_status(ctx, db, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/parse/runs/{run_id}/blocks", response_model=ParseBlocksResponse)
async def get_parse_run_blocks(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    run_id: UUID,
) -> ParseBlocksResponse:
    try:
        return await parse_service.get_parse_blocks(ctx, db, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
