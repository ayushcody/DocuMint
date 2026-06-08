from __future__ import annotations

import asyncio
import io
import os
from pathlib import Path
from uuid import UUID

import pytest
from PIL import Image

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_colpali_embedding_shape() -> None:
    pytest.importorskip("colpali_engine")
    pytest.importorskip("torch")
    _require_colqwen2_cache()

    from workers.indexing import embed_page_colpali

    image_bytes = _test_image_bytes()
    patches = await embed_page_colpali(image_bytes)

    assert isinstance(patches, list)
    assert len(patches) > 0
    assert len(patches[0]) == 128
    assert all(isinstance(value, float) for value in patches[0])


@pytest.mark.asyncio
async def test_qdrant_collection_create_and_upsert() -> None:
    pytest.importorskip("colpali_engine")
    qdrant_client = pytest.importorskip("qdrant_client")

    from workers.indexing import create_colpali_collection, index_page

    client = qdrant_client.QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    await _require_qdrant(client)
    collection_name = "test_smoke_colpali"

    await create_colpali_collection(client, collection_name)
    collections = await asyncio.to_thread(client.get_collections)
    assert collection_name in [collection.name for collection in collections.collections]

    await index_page(
        client=client,
        collection_name=collection_name,
        workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=UUID("00000000-0000-0000-0000-000000000002"),
        page_num=0,
        page_image_bytes=_test_image_bytes(color=(240, 240, 240)),
        parse_blocks=[],
    )
    results = await asyncio.to_thread(client.scroll, collection_name=collection_name, limit=1)
    assert len(results[0]) == 1

    await asyncio.to_thread(client.delete_collection, collection_name)


@pytest.mark.asyncio
async def test_retrieval_returns_real_results() -> None:
    pytest.importorskip("colpali_engine")
    qdrant_client = pytest.importorskip("qdrant_client")

    from workers.indexing import create_colpali_collection, index_page, query_colpali_collection

    workspace_id = UUID("00000000-0000-0000-0000-000000000001")
    client = qdrant_client.QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    await _require_qdrant(client)
    collection_name = "test_smoke_retrieval"

    await create_colpali_collection(client, collection_name)
    for page_num in range(3):
        await index_page(
            client=client,
            collection_name=collection_name,
            workspace_id=workspace_id,
            document_id=UUID("00000000-0000-0000-0000-000000000003"),
            page_num=page_num,
            page_image_bytes=_test_image_bytes(color=(200 + page_num * 20,) * 3),
            parse_blocks=[],
        )

    hits = await query_colpali_collection(collection_name, "total amount due", workspace_id, 3)
    assert isinstance(hits, list)
    assert len(hits) > 0
    assert "score" in hits[0]
    assert float(hits[0]["score"]) >= 0.0

    await asyncio.to_thread(client.delete_collection, collection_name)


async def _require_qdrant(client: object) -> None:
    try:
        await asyncio.to_thread(client.get_collections)
    except Exception as exc:
        pytest.skip(f"Qdrant is not reachable: {exc}")


def _test_image_bytes(color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    image = Image.new("RGB", (800, 1000), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _require_colqwen2_cache() -> None:
    cache_dir = Path(os.getenv("DOCUMINT_MODEL_CACHE_DIR", "~/.cache/documint/models")).expanduser()
    base_snapshots = cache_dir / "models--vidore--colqwen2-base" / "snapshots"
    if not base_snapshots.exists():
        pytest.skip("ColQwen2 base model is not cached")
    snapshots = [path for path in base_snapshots.iterdir() if path.is_dir()]
    if not snapshots:
        pytest.skip("ColQwen2 base model has no cached snapshot")
    latest = max(snapshots, key=lambda path: path.stat().st_mtime)
    missing = [
        name
        for name in ("model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors")
        if not (latest / name).exists()
    ]
    if missing:
        pytest.skip(f"ColQwen2 base model cache is incomplete: {', '.join(missing)}")
