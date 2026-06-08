from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, WorkspaceScopedMixin


class ParseRun(WorkspaceScopedMixin, Base):
    __tablename__ = "parse_runs"

    document_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("documents.id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_credits: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    config_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    agent_timings_ms: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ParseBlockRow(WorkspaceScopedMixin, Base):
    __tablename__ = "parse_blocks"

    parse_run_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("parse_runs.id"))
    block_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    bbox: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    ast: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    citations_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    verifier: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    reading_order_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
