from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, WorkspaceScopedMixin


class Citation(WorkspaceScopedMixin, Base):
    __tablename__ = "citations"

    parse_block_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("parse_blocks.id"),
        nullable=True,
    )
    extraction_run_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("extraction_runs.id"),
        nullable=True,
    )
    field_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    matching_text: Mapped[str] = mapped_column(Text, nullable=False)
    bboxes: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
