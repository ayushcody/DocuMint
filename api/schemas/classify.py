from __future__ import annotations

from uuid import UUID

from pydantic import Field

from api.schemas.common import StrictBaseModel


class TaxonomyItem(StrictBaseModel):
    label: str
    description: str | None = None


class PageClassification(StrictBaseModel):
    page_num: int = Field(ge=0)
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    scores: dict[str, float] = Field(default_factory=dict)
    model: str


class ClassifyRunRequest(StrictBaseModel):
    parse_run_id: UUID
    taxonomy: list[str | TaxonomyItem] = Field(min_length=1)


class ClassifyRunResponse(StrictBaseModel):
    run_id: UUID
    page_labels: dict[int, str]
    classifications: list[PageClassification] = Field(default_factory=list)
