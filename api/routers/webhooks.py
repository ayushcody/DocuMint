from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext, get_db, get_workspace_context
from api.models.webhook import WebhookEndpoint
from api.schemas.webhooks import WebhookEndpointCreateRequest, WebhookEndpointCreateResponse

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/endpoints", response_model=WebhookEndpointCreateResponse)
async def create_webhook_endpoint(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: WebhookEndpointCreateRequest,
) -> WebhookEndpointCreateResponse:
    if body.url.scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="webhook URL must use https",
        )
    endpoint = WebhookEndpoint(
        workspace_id=ctx.workspace_id,
        url=str(body.url),
        events=body.events,
        status="registered",
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    return WebhookEndpointCreateResponse(
        endpoint_id=endpoint.id,
        url=body.url,
        events=endpoint.events,
        status=endpoint.status,
    )
