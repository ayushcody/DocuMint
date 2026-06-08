from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends

from api.deps import WorkspaceContext, get_workspace_context
from api.schemas.evals import (
    EvalRunRequest,
    EvalRunResponse,
    EvalSuiteCreateRequest,
    EvalSuiteCreateResponse,
)

router = APIRouter(prefix="/v1/evals", tags=["evals"])


@router.post("/suites", response_model=EvalSuiteCreateResponse)
async def create_eval_suite(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    body: EvalSuiteCreateRequest,
) -> EvalSuiteCreateResponse:
    del ctx
    return EvalSuiteCreateResponse(suite_id=uuid4(), name=body.name)


@router.post("/runs", response_model=EvalRunResponse)
async def create_eval_run(
    ctx: Annotated[WorkspaceContext, Depends(get_workspace_context)],
    body: EvalRunRequest,
) -> EvalRunResponse:
    del ctx, body
    return EvalRunResponse(
        run_id=uuid4(),
        scores={"table_teds": 0.0, "retrieval_ndcg_at_5": 0.0, "confidence_ece": 0.0},
    )
