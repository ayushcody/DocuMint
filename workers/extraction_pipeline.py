from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from api.deps import open_workspace_session
from api.models.extraction import ExtractionRun, ExtractionSchema
from api.models.parse import ParseBlockRow
from api.services.extract_service import _extraction_citation_rows
from celery_app import celery_app
from workers.extraction import build_structured_prompt, extract_schema_fields

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, name="workers.extraction_pipeline.run_extraction")
def run_extraction_task(self: object, extraction_run_id: str, workspace_id: str) -> None:
    asyncio.run(_async_extraction(self, UUID(extraction_run_id), UUID(workspace_id)))


async def _async_extraction(task: object, extraction_run_id: UUID, workspace_id: UUID) -> None:
    async with open_workspace_session(workspace_id) as db:
        run = await db.get(ExtractionRun, extraction_run_id)
        if run is None or run.workspace_id != workspace_id:
            logger.error(
                "ExtractionRun %s not found in workspace %s",
                extraction_run_id,
                workspace_id,
            )
            return

        try:
            run.status = "running"
            await db.commit()

            schema = await db.get(ExtractionSchema, run.schema_id)
            if schema is None or schema.workspace_id != workspace_id:
                raise LookupError(f"Extraction schema {run.schema_id} not found")

            blocks_result = await db.execute(
                select(ParseBlockRow)
                .where(ParseBlockRow.parse_run_id == run.parse_run_id)
                .where(ParseBlockRow.workspace_id == workspace_id)
                .order_by(ParseBlockRow.page, ParseBlockRow.reading_order_rank)
            )
            parse_blocks = [row.ast for row in blocks_result.scalars()]
            if not parse_blocks:
                raise LookupError(f"Parse run {run.parse_run_id} has no parse blocks")

            data, metadata = await extract_schema_fields(schema.json_schema, parse_blocks)
            prompt = build_structured_prompt(schema.json_schema, parse_blocks)

            run.data = data
            run.field_metadata = {**metadata, "_prompt": {"text": prompt}}
            run.status = "complete"
            db.add_all(_extraction_citation_rows(workspace_id, extraction_run_id, metadata))
            await db.commit()
            logger.info("Extraction %s complete", extraction_run_id)
        except Exception as exc:
            logger.exception("Extraction %s failed", extraction_run_id)
            run.status = "failed"
            run.data = {}
            run.field_metadata = {"_error": {"message": str(exc)}}
            await db.commit()
            retry = getattr(task, "retry", None)
            if callable(retry):
                raise retry(exc=exc, countdown=10) from exc
            raise
