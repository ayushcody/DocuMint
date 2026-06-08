from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.getenv("DOCUMINT_JWT_SECRET")
JWT_ALGORITHM = os.getenv("DOCUMINT_JWT_ALGORITHM", "HS256")
JWT_AUDIENCE = os.getenv("DOCUMINT_JWT_AUDIENCE", "documint-api")

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    workspace_id: UUID
    actor_id: str


def _decode_jwt_verified(token: str) -> dict[str, object]:
    if not JWT_SECRET:
        raise RuntimeError(
            "DOCUMINT_JWT_SECRET environment variable is not set. "
            "Generate one: openssl rand -hex 32"
        )
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT payload must be an object.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must be a Bearer token.",
        )
    return token


async def get_workspace_id(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
) -> UUID:
    token = _extract_bearer_token(authorization)
    if token is not None:
        payload = _decode_jwt_verified(token)
        workspace_candidate = payload.get("workspace_id") or payload.get("sub")
        if workspace_candidate is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT missing workspace_id claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return UUID(str(workspace_candidate))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT workspace_id is not a valid UUID.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    if x_workspace_id is not None:
        dev_mode = os.getenv("DOCUMINT_DEV_MODE", "false").lower() == "true"
        if not dev_mode:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "X-Workspace-Id header is only accepted in dev mode. "
                    "Set DOCUMINT_DEV_MODE=true for local development. "
                    "Use Authorization: Bearer <jwt> in production."
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return UUID(x_workspace_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="X-Workspace-Id is not a valid UUID.",
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No authentication provided. Use Authorization: Bearer <jwt>.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_actor_id(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> str:
    token = _extract_bearer_token(authorization)
    if token is not None:
        payload = _decode_jwt_verified(token)
        actor = payload.get("sub") or payload.get("actor_id") or payload.get("email")
        if actor is not None:
            return str(actor)
    if os.getenv("DOCUMINT_DEV_MODE", "false").lower() == "true":
        return x_actor_id or "api"
    if x_actor_id is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Actor-Id header is only accepted in dev mode.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "api"


async def apply_workspace_rls(session: AsyncSession, workspace_id: UUID) -> None:
    await session.execute(text(f"SET LOCAL app.workspace_id = '{workspace_id}'"))


async def get_db(
    workspace_id: Annotated[UUID, Depends(get_workspace_id)],
) -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            await apply_workspace_rls(session, workspace_id)
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


@asynccontextmanager
async def open_workspace_session(workspace_id: UUID) -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            await apply_workspace_rls(session, workspace_id)
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


async def get_workspace_context(
    workspace_id: Annotated[UUID, Depends(get_workspace_id)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> WorkspaceContext:
    return WorkspaceContext(workspace_id=workspace_id, actor_id=actor_id)
