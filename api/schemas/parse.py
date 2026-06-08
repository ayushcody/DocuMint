from __future__ import annotations

from uuid import UUID

from pydantic import Field, HttpUrl

from api.schemas.common import ParseBlock, RunStatus, StrictBaseModel


class FileUploadResponse(StrictBaseModel):
    file_id: UUID
    object_path: str
    sha256: str


class ParseConfig(StrictBaseModel):
    use_vlm: bool = True
    enable_colpali: bool = True
    document_anchoring: bool = True
    enable_verifier: bool = True
    table_stitching: bool = True
    calibrate_confidence: bool = True
    webhook_url: HttpUrl | None = None


class ParseRunRequest(StrictBaseModel):
    file_id: UUID
    config: ParseConfig = Field(default_factory=ParseConfig)


class ParseRunCreateResponse(StrictBaseModel):
    job_id: UUID
    status: RunStatus


class ParseRunStatusResponse(StrictBaseModel):
    id: UUID
    status: RunStatus
    progress: float = Field(ge=0.0, le=1.0)
    cost_credits: float = Field(ge=0.0)
    agent_timings_ms: dict[str, int]
    error: str | None = None


class ParseBlocksResponse(StrictBaseModel):
    run_id: UUID
    status: RunStatus
    pages_done: int = Field(ge=0)
    pages_total: int = Field(ge=0)
    blocks: list[ParseBlock]
