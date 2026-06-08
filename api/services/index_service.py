from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import WorkspaceContext
from api.models.document import Document
from api.models.index import Chunk, IndexCollection
from api.models.parse import ParseBlockRow, ParseRun
from api.schemas.common import BBox
from api.schemas.index import (
    CollectionCreateResponse,
    CollectionSyncResponse,
    RetrievalHit,
    RetrievalQueryResponse,
)
from api.services import storage
from workers.indexing import (
    create_colpali_collection,
    index_page_colpali,
    qdrant_collection_name,
    query_colpali_collection,
)


async def create_collection(
    ctx: WorkspaceContext,
    db: AsyncSession,
    name: str,
    enable_binary_quantization: bool,
) -> CollectionCreateResponse:
    collection_id = uuid4()
    collection = IndexCollection(
        id=collection_id,
        workspace_id=ctx.workspace_id,
        name=name,
        enable_binary_quantization=enable_binary_quantization,
    )
    db.add(collection)
    await db.commit()
    return CollectionCreateResponse(collection_id=collection_id, name=name)


async def sync_collection(
    ctx: WorkspaceContext,
    db: AsyncSession,
    collection_id: UUID,
    parse_run_ids: list[UUID],
) -> CollectionSyncResponse:
    await _require_collection(ctx, db, collection_id)
    collection_name = qdrant_collection_name(collection_id)
    await create_colpali_collection(collection_name)

    queued_documents = 0
    pages_indexed = 0
    for parse_run_id in parse_run_ids:
        parse_run = await _require_parse_run(ctx, db, parse_run_id)
        document = await _require_document(ctx, db, parse_run.document_id)
        parse_blocks = await _load_parse_block_asts(ctx, db, parse_run_id)
        for page_num in sorted({int(block.get("page", 0)) for block in parse_blocks}):
            render_path = storage.render_path(ctx.workspace_id, document.id, page_num)
            render_bytes = await storage.get_object(render_path)
            point_id = await index_page_colpali(
                collection_name=collection_name,
                workspace_id=ctx.workspace_id,
                document_id=document.id,
                page_num=page_num,
                page_image_bytes=render_bytes,
                parse_blocks=parse_blocks,
            )
            page_blocks = [
                block for block in parse_blocks if int(block.get("page", -1)) == page_num
            ]
            db.add(
                Chunk(
                    id=uuid4(),
                    workspace_id=ctx.workspace_id,
                    document_id=document.id,
                    parse_run_id=parse_run_id,
                    page=page_num,
                    text="\n".join(str(block.get("text", "")) for block in page_blocks),
                    bbox=_page_bbox(page_blocks),
                    vector_ref=point_id,
                    metadata_json={
                        "collection_id": str(collection_id),
                        "qdrant_collection": collection_name,
                        "qdrant_point_id": point_id,
                        "image_patch_path": render_path,
                        "block_ids": [str(block.get("block_id")) for block in page_blocks],
                    },
                )
            )
            pages_indexed += 1
        queued_documents += 1

    await db.commit()
    return CollectionSyncResponse(
        collection_id=collection_id,
        queued_documents=queued_documents,
        pages_indexed=pages_indexed,
        status="ready",
    )


async def query_collection(
    ctx: WorkspaceContext,
    db: AsyncSession,
    collection_id: UUID,
    query: str,
    limit: int,
) -> RetrievalQueryResponse:
    await _require_collection(ctx, db, collection_id)
    hits = await query_colpali_collection(
        collection_name=qdrant_collection_name(collection_id),
        query_text=query,
        workspace_id=ctx.workspace_id,
        limit=limit,
    )
    return RetrievalQueryResponse(
        hits=[
            RetrievalHit(
                document_id=UUID(str(hit["document_id"])),
                page_num=int(hit["page_num"]),
                score=float(hit["score"]),
                block_ids=[str(block_id) for block_id in hit.get("block_ids", [])],
                bbox=BBox(x=0.0, y=0.0, w=1.0, h=1.0, coord_space="page_norm"),
                image_patch_path=storage.render_path(
                    ctx.workspace_id,
                    UUID(str(hit["document_id"])),
                    int(hit["page_num"]),
                ),
            )
            for hit in hits
        ]
    )


async def _require_collection(
    ctx: WorkspaceContext,
    db: AsyncSession,
    collection_id: UUID,
) -> IndexCollection:
    result = await db.execute(
        select(IndexCollection)
        .where(IndexCollection.id == collection_id)
        .where(IndexCollection.workspace_id == ctx.workspace_id)
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise KeyError(f"collection_id not found in workspace: {collection_id}")
    return collection


async def _require_parse_run(
    ctx: WorkspaceContext,
    db: AsyncSession,
    parse_run_id: UUID,
) -> ParseRun:
    result = await db.execute(
        select(ParseRun)
        .where(ParseRun.id == parse_run_id)
        .where(ParseRun.workspace_id == ctx.workspace_id)
    )
    parse_run = result.scalar_one_or_none()
    if parse_run is None:
        raise KeyError(f"parse_run_id not found in workspace: {parse_run_id}")
    return parse_run


async def _require_document(
    ctx: WorkspaceContext,
    db: AsyncSession,
    document_id: UUID,
) -> Document:
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.workspace_id == ctx.workspace_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise KeyError(f"document_id not found in workspace: {document_id}")
    return document


async def _load_parse_block_asts(
    ctx: WorkspaceContext,
    db: AsyncSession,
    parse_run_id: UUID,
) -> list[dict[str, object]]:
    result = await db.execute(
        select(ParseBlockRow)
        .where(ParseBlockRow.parse_run_id == parse_run_id)
        .where(ParseBlockRow.workspace_id == ctx.workspace_id)
        .order_by(ParseBlockRow.page, ParseBlockRow.reading_order_rank)
    )
    rows = list(result.scalars())
    if not rows:
        raise KeyError(f"parse_run_id has no parse blocks: {parse_run_id}")
    return [row.ast for row in rows]


def _page_bbox(blocks: list[dict[str, object]]) -> dict[str, object]:
    if not blocks:
        return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "coord_space": "page_norm"}
    x1 = 1.0
    y1 = 1.0
    x2 = 0.0
    y2 = 0.0
    for block in blocks:
        bbox = block.get("bbox", {})
        if not isinstance(bbox, dict):
            continue
        x = float(bbox.get("x", 0.0))
        y = float(bbox.get("y", 0.0))
        w = float(bbox.get("w", 0.0))
        h = float(bbox.get("h", 0.0))
        x1 = min(x1, x)
        y1 = min(y1, y)
        x2 = max(x2, x + w)
        y2 = max(y2, y + h)
    if x2 <= x1 or y2 <= y1:
        return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "coord_space": "page_norm"}
    return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "coord_space": "page_norm"}
