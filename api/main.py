from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.ml_preflight import check_required_models
from api.routers import (
    artifacts,
    classify,
    evals,
    extract,
    health,
    index,
    parse,
    retrieval,
    reviews,
    split,
    webhooks,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not os.getenv("DOCUMINT_JWT_SECRET"):
        raise RuntimeError(
            "DOCUMINT_JWT_SECRET environment variable is not set. "
            "Generate one: openssl rand -hex 32"
        )
    check_required_models()
    app.state.service_name = "documind-api"
    yield


app = FastAPI(
    title="DocuMind AI",
    version="0.1.0",
    summary="Agentic Document AI API with transparent verification and bbox citations.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router)
app.include_router(health.router)
app.include_router(artifacts.router)
app.include_router(extract.router)
app.include_router(index.router)
app.include_router(retrieval.router)
app.include_router(classify.router)
app.include_router(split.router)
app.include_router(reviews.router)
app.include_router(evals.router)
app.include_router(webhooks.router)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
