from __future__ import annotations

from enum import StrEnum
from typing import Literal, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

JsonValue: TypeAlias = str | int | float | bool | None | dict[str, object] | list[object]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    intake_complete = "intake_complete"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class BBox(StrictBaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)
    coord_space: Literal["page_norm"] = "page_norm"


class VerifierComponents(StrictBaseModel):
    ssim: float = Field(ge=0.0, le=1.0)
    ocr_consistency: float = Field(ge=0.0, le=1.0)
    layout_iou: float = Field(ge=0.0, le=1.0)
    clip_sim: float = Field(ge=0.0, le=1.0)


class VerifierScore(StrictBaseModel):
    score: float = Field(ge=0.0, le=1.0)
    components: VerifierComponents
    L_verify: float = Field(ge=0.0)
    flag_for_repair: bool


class ConfidenceScore(StrictBaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    calibrated: float = Field(ge=0.0, le=1.0)
    raw: float = Field(ge=0.0, le=1.0)
    uncalibrated: float | None = Field(default=None, ge=0.0, le=1.0, deprecated=True)

    @model_validator(mode="before")
    @classmethod
    def _backfill_raw_confidence(cls, data: object) -> object:
        if isinstance(data, dict):
            values = cast(dict[str, object], data)
            if "raw" not in values and "uncalibrated" in values:
                values["raw"] = values["uncalibrated"]
            if "uncalibrated" not in values and "raw" in values:
                values["uncalibrated"] = values["raw"]
        return data


class Citation(StrictBaseModel):
    page: int = Field(ge=0)
    matching_text: str
    bboxes: list[BBox]


class ParseBlockSource(StrictBaseModel):
    native_pdf: bool
    ocr_engine: str
    vlm_engine: str
    verifier: VerifierScore
    crop_path: str | None = None
    render_path: str | None = None
    layout_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    layout_backend: str | None = None
    layout_backend_version: str | None = None
    warning: str | None = None
    prompt: str | None = None


class ParseBlock(StrictBaseModel):
    block_id: str = Field(pattern=r"^blk_[a-zA-Z0-9_-]+$")
    page: int = Field(ge=0)
    type: Literal[
        "table",
        "paragraph",
        "header",
        "figure",
        "equation",
        "form",
        "handwriting",
        "footer",
    ]
    bbox: BBox
    reading_order_rank: int = Field(ge=0)
    text: str
    html: str
    children: list[str] = Field(default_factory=list)
    source: ParseBlockSource
    confidence: ConfidenceScore
    citations: list[Citation] = Field(default_factory=list)
