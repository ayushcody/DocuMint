from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    profile: str
    services: dict[str, str]
    models: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    profile = os.getenv("DOCUMINT_PROFILE", "full")
    services = {
        "postgres": await _postgres_status(),
        "redis": _redis_status(),
        "minio": _minio_status(),
        "qdrant": _qdrant_status(),
    }
    models = {
        "sentence_transformer": _import_status("sentence_transformers"),
        "colqwen2": _colqwen2_status(),
        "weasyprint": _import_status("weasyprint"),
        "rapidocr": _import_status("rapidocr_onnxruntime"),
    }
    service_ok = all(value == "ok" for value in services.values())
    model_ok = all(value in {"available", "cached"} for value in models.values())
    return HealthResponse(
        status="ok" if service_ok and model_ok else "degraded",
        profile=profile,
        services=services,
        models=models,
    )


async def _postgres_status() -> str:
    try:
        from api.deps import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"error: {str(exc)[:80]}"


def _redis_status() -> str:
    try:
        import redis  # type: ignore[import-not-found]

        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        client.ping()
        return "ok"
    except Exception as exc:
        return f"error: {str(exc)[:80]}"


def _minio_status() -> str:
    try:
        import aioboto3  # noqa: F401

        if not os.getenv("MINIO_ENDPOINT_URL"):
            return "configured" if os.getenv("MINIO_SECRET_ACCESS_KEY") else "missing config"
        return "configured"
    except Exception:
        return "missing"


def _qdrant_status() -> str:
    try:
        from qdrant_client import QdrantClient  # type: ignore[import-not-found]

        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), timeout=2)
        client.get_collections()
        return "ok"
    except Exception as exc:
        return f"error: {str(exc)[:80]}"


def _import_status(module_name: str) -> str:
    try:
        __import__(module_name)
        return "available"
    except Exception:
        return "missing"


def _colqwen2_status() -> str:
    try:
        from colpali_engine.models import ColQwen2  # noqa: F401
    except Exception:
        return "missing"

    try:
        from scripts.check_models import CACHE_DIR, _latest_snapshot, _missing_shards

        adapter = _latest_snapshot("vidore--colqwen2-v1.0")
        base = _latest_snapshot("vidore--colqwen2-base")
        if adapter is None:
            return "missing adapter"
        if base is None:
            return "missing base"
        missing = _missing_shards(base)
        if missing:
            return f"incomplete base: {', '.join(missing[:2])}"
        return f"cached: {CACHE_DIR}"
    except Exception as exc:
        return f"importable, cache unknown: {str(exc)[:80]}"
