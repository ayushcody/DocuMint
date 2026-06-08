from __future__ import annotations

import os
from uuid import UUID

import pytest
from jose import jwt

TEST_JWT_SECRET = "test-secret-not-for-production"
TEST_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://documind:test@localhost:5432/documind")
os.environ.setdefault("DOCUMINT_JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("DOCUMINT_JWT_ALGORITHM", "HS256")
os.environ.setdefault("DOCUMINT_JWT_AUDIENCE", "documint-api")
os.environ.setdefault("DOCUMINT_DEV_MODE", "true")
os.environ.setdefault("MINIO_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY_ID", "documind")
os.environ.setdefault("MINIO_SECRET_ACCESS_KEY", "test-secret-not-for-production")
os.environ.setdefault("MINIO_BUCKET", "documind-test")


def make_test_jwt(workspace_id: str | UUID = TEST_WORKSPACE_ID) -> str:
    return jwt.encode(
        {
            "workspace_id": str(workspace_id),
            "sub": str(workspace_id),
            "aud": "documint-api",
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests that require external services or heavy models",
    )
    parser.addoption(
        "--regression",
        action="store_true",
        default=False,
        help="run golden-set regression tests",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_integration = pytest.mark.skip(reason="need --integration option to run")
    skip_regression = pytest.mark.skip(reason="need --regression option to run")
    run_integration = bool(config.getoption("--integration"))
    run_regression = bool(config.getoption("--regression"))

    for item in items:
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)
        if "regression" in item.keywords and not run_regression:
            item.add_marker(skip_regression)
