from __future__ import annotations

from uuid import UUID

from pydantic import HttpUrl

from api.schemas.common import StrictBaseModel


class WebhookEndpointCreateRequest(StrictBaseModel):
    url: HttpUrl
    events: list[str]


class WebhookEndpointCreateResponse(StrictBaseModel):
    endpoint_id: UUID
    url: HttpUrl
    events: list[str]
    status: str
