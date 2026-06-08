from __future__ import annotations

import asyncio
import io
import logging
import os
import uuid
from pathlib import Path
from uuid import UUID

import httpx
import numpy as np
from numpy.typing import NDArray
from PIL import Image

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLPALI_MODEL_ID = os.getenv("DOCUMINT_COLPALI_MODEL", "vidore/colqwen2-v1.0")
COLPALI_CACHE_DIR = os.getenv(
    "DOCUMINT_MODEL_CACHE_DIR",
    os.path.expanduser("~/.cache/documint/models"),
)
COLPALI_OFFLINE = os.getenv("DOCUMINT_COLPALI_OFFLINE", "false").lower() == "true"
COLPALI_EMBEDDING_DIM = 128
VECTOR_SIZE = COLPALI_EMBEDDING_DIM
_QDRANT_PAGE_NAMESPACE = uuid.UUID("7f3a2b1c-4d5e-6f70-8a9b-0c1d2e3f4a5b")

_colpali_model: object | None = None
_colpali_processor: object | None = None


async def embed_page_colpali(page_image_bytes: bytes) -> list[list[float]]:
    def encode() -> list[list[float]]:
        import torch  # type: ignore[import-not-found]

        model, processor = _get_colpali()
        image = Image.open(io.BytesIO(page_image_bytes)).convert("RGB")
        inputs = processor.process_images([image])
        inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.no_grad():
            embeddings = model(**inputs)
        return embeddings[0].cpu().float().tolist()

    return await asyncio.to_thread(encode)


async def create_colpali_collection(
    client_or_collection_name: object,
    collection_name: str | None = None,
) -> None:
    if collection_name is None:
        client = None
        resolved_collection_name = str(client_or_collection_name)
    else:
        client = client_or_collection_name
        resolved_collection_name = collection_name

    def create() -> None:
        from qdrant_client.models import (  # type: ignore[import-not-found]
            BinaryQuantization,
            BinaryQuantizationConfig,
            Distance,
            MultiVectorComparator,
            MultiVectorConfig,
            VectorParams,
        )

        qdrant_client = client
        if qdrant_client is None:
            from qdrant_client import QdrantClient  # type: ignore[import-not-found]

            qdrant_client = QdrantClient(url=QDRANT_URL)

        qdrant_client.recreate_collection(
            collection_name=resolved_collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM,
                ),
            ),
            quantization_config=BinaryQuantization(
                binary=BinaryQuantizationConfig(always_ram=True),
            ),
        )

    await asyncio.to_thread(create)


async def index_page_colpali(
    collection_name: str,
    workspace_id: UUID,
    document_id: UUID,
    page_num: int,
    page_image_bytes: bytes,
    parse_blocks: list[dict[str, object]],
) -> str:
    patch_vectors = await embed_page_colpali(page_image_bytes)
    point_id = _stable_page_point_id(document_id, page_num)

    def upsert() -> None:
        from qdrant_client import QdrantClient  # type: ignore[import-not-found]
        from qdrant_client.models import PointStruct  # type: ignore[import-not-found]

        client = QdrantClient(url=QDRANT_URL)
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=patch_vectors,
                    payload={
                        "workspace_id": str(workspace_id),
                        "document_id": str(document_id),
                        "page_num": page_num,
                        "block_ids": [
                            str(block["block_id"])
                            for block in parse_blocks
                            if int(block.get("page", -1)) == page_num
                        ],
                    },
                )
            ],
        )

    await asyncio.to_thread(upsert)
    return point_id


async def index_page(
    client: object,
    collection_name: str,
    workspace_id: str | UUID,
    document_id: str | UUID,
    page_num: int,
    page_image_bytes: bytes,
    parse_blocks: list[dict[str, object]],
) -> str:
    workspace_uuid = workspace_id if isinstance(workspace_id, UUID) else UUID(str(workspace_id))
    document_uuid = document_id if isinstance(document_id, UUID) else UUID(str(document_id))
    patch_vectors = await embed_page_colpali(page_image_bytes)
    point_id = _stable_page_point_id(document_uuid, page_num)

    def upsert() -> None:
        from qdrant_client.models import PointStruct  # type: ignore[import-not-found]

        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=patch_vectors,
                    payload={
                        "workspace_id": str(workspace_uuid),
                        "document_id": str(document_uuid),
                        "page_num": page_num,
                        "block_ids": [
                            str(block["block_id"])
                            for block in parse_blocks
                            if int(block.get("page", -1)) == page_num
                        ],
                    },
                )
            ],
        )

    await asyncio.to_thread(upsert)
    return point_id


async def query_colpali_collection(
    collection_name: str,
    query_text: str,
    workspace_id: UUID,
    limit: int,
) -> list[dict[str, object]]:
    query_vectors = await embed_query_colpali(query_text)

    def search() -> list[dict[str, object]]:
        from qdrant_client import QdrantClient  # type: ignore[import-not-found]  # noqa: I001
        from qdrant_client.models import FieldCondition, Filter, MatchValue  # type: ignore[import-not-found]

        client = QdrantClient(url=QDRANT_URL)
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vectors,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="workspace_id",
                        match=MatchValue(value=str(workspace_id)),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "document_id": result.payload["document_id"],
                "page_num": result.payload["page_num"],
                "score": float(result.score),
                "block_ids": result.payload.get("block_ids", []),
            }
            for result in results
        ]

    return await asyncio.to_thread(search)


async def embed_query_colpali(query_text: str) -> list[list[float]]:
    def encode() -> list[list[float]]:
        import torch  # type: ignore[import-not-found]

        model, processor = _get_colpali()
        inputs = processor.process_queries([query_text])
        inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.no_grad():
            embeddings = model(**inputs)
        return embeddings[0].cpu().float().tolist()

    return await asyncio.to_thread(encode)


def _get_colpali() -> tuple[object, object]:
    global _colpali_model, _colpali_processor
    if _colpali_model is None or _colpali_processor is None:
        import torch  # type: ignore[import-not-found]  # noqa: I001
        from colpali_engine.models import ColQwen2, ColQwen2Processor  # type: ignore[import-not-found]

        device = (
            "mps"
            if (
                getattr(torch.backends, "mps", None) is not None
                and torch.backends.mps.is_available()
            )
            else "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )
        dtype = torch.bfloat16 if device in {"mps", "cuda"} else torch.float32
        model_path = _cached_snapshot_path(COLPALI_MODEL_ID) or COLPALI_MODEL_ID
        use_local_files = COLPALI_OFFLINE or model_path != COLPALI_MODEL_ID
        model_kwargs = {
            "torch_dtype": dtype,
            "device_map": device,
            "cache_dir": COLPALI_CACHE_DIR,
            "local_files_only": use_local_files,
        }
        if use_local_files:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            _colpali_model = ColQwen2.from_pretrained(
                model_path,
                **model_kwargs,
            ).eval()
            _colpali_processor = ColQwen2Processor.from_pretrained(
                model_path,
                cache_dir=COLPALI_CACHE_DIR,
                local_files_only=use_local_files,
            )
        except Exception as exc:
            raise RuntimeError(
                f"ColQwen2 model is not available locally and download failed: {exc}\n"
                "Download it with: python scripts/download_models.py\n"
                "ColQwen2 requires both vidore/colqwen2-v1.0 and vidore/colqwen2-base.\n"
                f"Cache dir: {COLPALI_CACHE_DIR}\n"
                "Or set DOCUMINT_COLPALI_OFFLINE=false with working HuggingFace access."
            ) from exc
        logger.info("ColQwen2 model loaded: %s on %s", COLPALI_MODEL_ID, device)
    return _colpali_model, _colpali_processor


def _cached_snapshot_path(model_id: str) -> str | None:
    model_cache = Path(COLPALI_CACHE_DIR) / f"models--{model_id.replace('/', '--')}"
    snapshots = model_cache / "snapshots"
    if not snapshots.exists():
        return None
    candidates = [path for path in snapshots.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return str(max(candidates, key=lambda path: path.stat().st_mtime))


def maxsim_late_interaction(
    query_vectors: NDArray[np.float64],
    document_vectors: NDArray[np.float64],
) -> float:
    """
    MaxSim(Q,D) = sum_i max_j cosine(q_i, d_j).
    """
    q = _l2_normalize(query_vectors)
    d = _l2_normalize(document_vectors)
    similarities = q @ d.T
    return float(np.max(similarities, axis=1).sum())


def hybrid_retrieval_score(
    s_dense: float,
    s_sparse: float,
    s_visual: float,
    s_meta: float,
    s_rerank: float,
    alpha: float = 0.30,
    beta: float = 0.20,
    gamma: float = 0.30,
    delta: float = 0.10,
    epsilon: float = 0.10,
) -> float:
    return (
        alpha * s_dense
        + beta * s_sparse
        + gamma * s_visual
        + delta * s_meta
        + epsilon * s_rerank
    )


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return fused


def binary_quantize(embeddings: NDArray[np.float64]) -> NDArray[np.int8]:
    return np.where(embeddings >= 0, 1, -1).astype(np.int8)


async def _ensure_qdrant_collection(client: httpx.AsyncClient, collection_name: str) -> None:
    response = await client.put(
        f"{QDRANT_URL}/collections/{collection_name}",
        json={
            "vectors": {
                "patches": {
                    "size": VECTOR_SIZE,
                    "distance": "Cosine",
                    "multivector_config": {"comparator": "max_sim"},
                }
            },
            "quantization_config": {"binary": {"always_ram": True}},
        },
    )
    if response.status_code not in {200, 201}:
        response.raise_for_status()


def qdrant_collection_name(collection_id: UUID) -> str:
    return f"documind_{str(collection_id).replace('-', '_')}"


def _stable_page_point_id(document_id: UUID, page_num: int) -> str:
    return str(uuid.uuid5(_QDRANT_PAGE_NAMESPACE, f"{document_id}:{page_num}"))


def _collection_name(collection_id: UUID) -> str:
    return qdrant_collection_name(collection_id)


def _l2_normalize(vectors: NDArray[np.float64]) -> NDArray[np.float64]:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms
