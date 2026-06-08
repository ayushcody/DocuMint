from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, WorkspaceScopedMixin


class IndexCollection(WorkspaceScopedMixin, Base):
    __tablename__ = "index_collections"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    enable_binary_quantization: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Chunk(WorkspaceScopedMixin, Base):
    __tablename__ = "chunks"

    document_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    parse_run_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("parse_runs.id"),
        nullable=False,
    )
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    bbox: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    vector_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
