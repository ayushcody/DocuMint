from __future__ import annotations

from uuid import UUID

from api.schemas.common import BBox, StrictBaseModel


class ReviewActionRequest(StrictBaseModel):
    parse_run_id: UUID
    block_id: str
    corrected_text: str | None = None
    corrected_bbox: BBox | None = None
    mismatch_types: list[str]
    used_for_training: bool = False


class ReviewActionResponse(StrictBaseModel):
    action_id: UUID
    status: str
    used_for_training: bool
