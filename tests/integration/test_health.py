from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_health_endpoint_returns_dependency_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMINT_JWT_SECRET", "test-secret")

    from api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"ok", "degraded"}
    assert "postgres" in data["services"]
    assert "redis" in data["services"]
    assert "qdrant" in data["services"]
    assert "sentence_transformer" in data["models"]
    assert "colqwen2" in data["models"]
