# DocuMind AI

DocuMind AI is an open-core, agentic Document AI platform scaffolded from the project guideline. The first build focuses on the contracts that matter most: workspace isolation, parse-block transparency, verifier scores, calibrated confidence, bounding-box citations, and visual debugging.

## Structure

- `api/`: FastAPI app, routers, Pydantic schemas, service layer, and SQLAlchemy models.
- `workers/`: the seven-agent pipeline modules.
- `frontend/`: Next.js 14 parse debugger with canvas bbox overlays and Zustand sync.
- `infra/`: local Docker Compose services, Helm skeleton, and monitoring config.
- `golden_set/`: regression-set directories and expected artifact placeholders.
- `tests/`: unit tests for mathematical formulas and core contracts.

## Local Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn api.main:app --reload
```

All API requests require a signed JWT. `X-Workspace-Id` is accepted only when
`DOCUMINT_DEV_MODE=true` for local development:

```bash
Authorization: Bearer <signed-jwt>
```

## Local Frontend

```bash
cd frontend
npm install
npm run dev
```

## Local Services

```bash
docker compose -f infra/docker-compose.yml up
```

This starts PostgreSQL, Redis, MinIO, Qdrant, Prometheus, and Grafana for local development.

## Test Gates

```bash
pytest tests/unit -q
python scripts/generate_golden_set.py
pytest tests/regression -q --regression
make integration-test
```

Run the integration gate before merging changes that touch ColPali, Qdrant, MinIO, Celery, or the
verifier. The integration target expects Docker Compose services and full model dependencies to be
available locally.

### Verifier Renderer Runtime

Agent 5 uses a real HTML renderer for render-and-compare verification. The preferred local path is
WeasyPrint plus native Cairo/Pango libraries; Playwright Chromium is the fallback.

On macOS:

```bash
brew install cairo pango gdk-pixbuf libffi
.venv/bin/python -m playwright install chromium
```

On Debian/Ubuntu:

```bash
apt-get install -y \
  libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
  libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info
```

Verify the renderer:

```bash
pytest tests/integration/test_verifier_renderer.py -q --integration
```

Codex sandbox runs can block Chromium's macOS Mach port registration and Next/Turbopack internal
port binding. Run verifier and frontend build checks in a normal local shell or CI when that occurs.

### Model Cache

Classification, splitting, and visual RAG use HuggingFace models. Download them once before running
the full profile or set the services to offline mode after the cache is populated:

```bash
make download-models
make check-models
```

The default cache path is `~/.cache/documint/models`. Override it with
`DOCUMINT_MODEL_CACHE_DIR`. Visual RAG defaults to `vidore/colqwen2-v1.0`; classification and
semantic splitting default to `sentence-transformers/all-MiniLM-L6-v2`. If those models are not
cached and network access is unavailable, classification and splitting use the explicit lexical
fallback only when `DOCUMINT_CLASSIFY_ALLOW_LEXICAL_FALLBACK=true`.

### Extraction Backend

Extraction is asynchronous. `POST /v1/extract/runs` queues work, and
`GET /v1/extract/runs/{id}` polls for `queued`, `running`, `complete`, or `failed`.

`DOCUMINT_EXTRACTION_BACKEND=anthropic` is the default. Set `ANTHROPIC_API_KEY` for schema-guided
tool extraction, or use `DOCUMINT_EXTRACTION_BACKEND=openai_compat` with
`DOCUMINT_EXTRACTION_ENDPOINT` for a local OpenAI-compatible server. When no constrained backend is
configured, extraction logs the degraded path and falls back to deterministic citation-preserving
field matching.

## Deployment Profiles

`DOCUMINT_PROFILE` controls which model dependencies are required at startup:

```bash
DOCUMINT_PROFILE=parse_only     # Agents 1-4 only
DOCUMINT_PROFILE=parse_extract  # Agents 1-6, no RAG
DOCUMINT_PROFILE=rag_only       # Agent 7 indexing/retrieval only
DOCUMINT_PROFILE=full           # All 7 agents, default
```

RAG routes return HTTP 503 unless the profile is `full` or `rag_only`.

## Current Scope

This is a first-pass build scaffold. Heavy model integrations are intentionally represented as typed service stubs so the architecture can be tested and extended without pretending that YOLOv9, MinerU, olmOCR, ColPali, Triton, or vLLM are already deployed locally.
