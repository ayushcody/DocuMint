from __future__ import annotations

from uuid import UUID

import pytest
from conftest import TEST_WORKSPACE_ID, make_test_jwt
from fastapi import HTTPException

from api.deps import get_workspace_id


@pytest.mark.asyncio
async def test_get_workspace_id_rejects_missing_auth() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_workspace_id()

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_workspace_id_rejects_workspace_header_outside_dev_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCUMINT_DEV_MODE", "false")

    with pytest.raises(HTTPException) as exc_info:
        await get_workspace_id(x_workspace_id=TEST_WORKSPACE_ID)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_workspace_id_rejects_forged_jwt() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_workspace_id(authorization="Bearer forged.payload.signature")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_workspace_id_accepts_valid_signed_jwt() -> None:
    workspace_id = await get_workspace_id(authorization=f"Bearer {make_test_jwt()}")

    assert workspace_id == UUID(TEST_WORKSPACE_ID)
