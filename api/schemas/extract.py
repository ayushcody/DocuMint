from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from api.schemas.common import BBox, JsonValue, StrictBaseModel


class Citation(StrictBaseModel):
    page: int = Field(ge=0)
    matching_text: str
    bboxes: list[BBox] = Field(min_length=1)


class FieldConfidence(StrictBaseModel):
    calibrated: float = Field(ge=0.0, le=1.0)
    raw: float = Field(ge=0.0, le=1.0)


class FieldValidatorResult(StrictBaseModel):
    name: str
    pattern: str | None = None
    status: str


class FieldMetadata(StrictBaseModel):
    confidence: FieldConfidence
    citations: list[Citation] = Field(min_length=1)
    validators: list[FieldValidatorResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtractionSchemaCreateRequest(StrictBaseModel):
    name: str
    json_schema: dict[str, JsonValue]


class ExtractionSchemaCreateResponse(StrictBaseModel):
    schema_id: UUID
    name: str


class ExtractionRunRequest(StrictBaseModel):
    parse_run_id: UUID
    schema_id: UUID


class ExtractionRunResponse(StrictBaseModel):
    run_id: UUID
    status: Literal["queued"] = "queued"


class ExtractionResultResponse(StrictBaseModel):
    run_id: UUID
    status: Literal["queued", "running", "complete", "failed"]
    data: dict[str, JsonValue] | None = None
    field_metadata: dict[str, FieldMetadata] | None = None
    cost_credits: float | None = Field(default=None, ge=0.0)
    error: str | None = None
