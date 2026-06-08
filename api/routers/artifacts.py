from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import WorkspaceContext, get_workspace_context
from api.services import storage

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])


@router.get("/signed-url")
async def get_signed_artifact_url(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    path: Annotated[str, Query(min_length=1)],
    expires: Annotated[int, Query(ge=60, le=86400)] = 3600,
) -> dict[str, str]:
    normalized_path = path.lstrip("/")
    workspace_prefix = f"{ctx.workspace_id}/"
    if not normalized_path.startswith(workspace_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="artifact path is outside the current workspace",
        )
    return {"url": await storage.get_signed_url(normalized_path, expires=expires)}
