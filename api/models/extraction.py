from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, WorkspaceScopedMixin


class ExtractionSchema(WorkspaceScopedMixin, Base):
    __tablename__ = "extraction_schemas"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    json_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class ExtractionRun(WorkspaceScopedMixin, Base):
    __tablename__ = "extraction_runs"

    parse_run_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("parse_runs.id"))
    schema_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("extraction_schemas.id"),
    )
    data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    field_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
