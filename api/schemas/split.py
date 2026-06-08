from __future__ import annotations

from uuid import UUID

from pydantic import Field

from api.schemas.common import StrictBaseModel


class SplitRunRequest(StrictBaseModel):
    parse_run_id: UUID
    config: dict[str, object] = Field(default_factory=dict)


class SplitSegment(StrictBaseModel):
    segment_id: UUID
    start_page: int = Field(ge=0)
    end_page: int = Field(ge=0)
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    page_count: int | None = Field(default=None, ge=1)
    evidence: str | None = None


class SplitRunResponse(StrictBaseModel):
    run_id: UUID
    segments: list[SplitSegment]
