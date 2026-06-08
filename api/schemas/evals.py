from __future__ import annotations

from uuid import UUID

from pydantic import Field

from api.schemas.common import StrictBaseModel


class EvalSuiteCreateRequest(StrictBaseModel):
    name: str
    golden_set_paths: list[str] = Field(min_length=1)


class EvalSuiteCreateResponse(StrictBaseModel):
    suite_id: UUID
    name: str


class EvalRunRequest(StrictBaseModel):
    suite_id: UUID


class EvalRunResponse(StrictBaseModel):
    run_id: UUID
    scores: dict[str, float]
