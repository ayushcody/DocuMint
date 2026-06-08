from __future__ import annotations

from uuid import UUID

from pydantic import Field

from api.schemas.common import BBox, StrictBaseModel


class CollectionCreateRequest(StrictBaseModel):
    name: str
    enable_binary_quantization: bool = True
    embedding_model: str | None = None


class CollectionCreateResponse(StrictBaseModel):
    collection_id: UUID
    name: str


class CollectionSyncRequest(StrictBaseModel):
    parse_run_ids: list[UUID] | None = Field(default=None, min_length=1)
    parse_run_id: UUID | None = None

    def resolved_parse_run_ids(self) -> list[UUID]:
        if self.parse_run_ids:
            return self.parse_run_ids
        if self.parse_run_id:
            return [self.parse_run_id]
        raise ValueError("Either parse_run_ids or parse_run_id is required")


class CollectionSyncResponse(StrictBaseModel):
    collection_id: UUID
    queued_documents: int
    pages_indexed: int = 0
    status: str = "ready"


class RetrievalQueryRequest(StrictBaseModel):
    collection_id: UUID
    query: str
    limit: int = Field(default=5, ge=1, le=50)


class RetrievalHit(StrictBaseModel):
    document_id: UUID
    page_num: int = Field(ge=0)
    score: float = Field(ge=0.0)
    block_ids: list[str] = Field(default_factory=list)
    bbox: BBox
    image_patch_path: str


class RetrievalQueryResponse(StrictBaseModel):
    hits: list[RetrievalHit]
