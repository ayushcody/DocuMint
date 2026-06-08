from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, WorkspaceScopedMixin


class SplitRun(WorkspaceScopedMixin, Base):
    __tablename__ = "split_runs"

    parse_run_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("parse_runs.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    segments: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)


class ClassificationRun(WorkspaceScopedMixin, Base):
    __tablename__ = "classification_runs"

    parse_run_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("parse_runs.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    taxonomy: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    page_labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    scores: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
