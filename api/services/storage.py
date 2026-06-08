from __future__ import annotations

import inspect
import json
import os
from collections.abc import Iterable
from uuid import UUID

import aioboto3
from botocore.exceptions import ClientError

MINIO_ENDPOINT_URL = os.environ["MINIO_ENDPOINT_URL"]
MINIO_ACCESS_KEY_ID = os.environ["MINIO_ACCESS_KEY_ID"]
MINIO_SECRET_ACCESS_KEY = os.environ["MINIO_SECRET_ACCESS_KEY"]
MINIO_BUCKET = os.environ["MINIO_BUCKET"]
MINIO_REGION = os.getenv("MINIO_REGION", "us-east-1")


def _strip_leading_slash(path: str) -> str:
    return path.lstrip("/")


def _artifact_path(
    workspace_id: UUID | str,
    document_id: UUID | str,
    artifact_type: str,
    filename: str,
) -> str:
    return f"/{workspace_id}/{document_id}/{artifact_type}/{filename}"


def original_path(workspace_id: UUID | str, document_id: UUID | str, filename: str) -> str:
    return _artifact_path(workspace_id, document_id, "originals", filename)


def render_path(workspace_id: UUID | str, document_id: UUID | str, page_num: int) -> str:
    return _artifact_path(workspace_id, document_id, "renders", f"page_{page_num}.png")


def crop_path(workspace_id: UUID | str, document_id: UUID | str, block_id: str) -> str:
    return _artifact_path(workspace_id, document_id, "crops", f"{block_id}.png")


def ast_path(workspace_id: UUID | str, document_id: UUID | str, parse_run_id: UUID | str) -> str:
    return _artifact_path(workspace_id, document_id, "ast", f"parse_run_{parse_run_id}.json")


def log_path(workspace_id: UUID | str, document_id: UUID | str, parse_run_id: UUID | str) -> str:
    return _artifact_path(workspace_id, document_id, "logs", f"parse_run_{parse_run_id}.jsonl")


def _client_kwargs() -> dict[str, str]:
    return {
        "endpoint_url": MINIO_ENDPOINT_URL,
        "aws_access_key_id": MINIO_ACCESS_KEY_ID,
        "aws_secret_access_key": MINIO_SECRET_ACCESS_KEY,
        "region_name": MINIO_REGION,
    }


async def _ensure_bucket_exists(client: object) -> None:
    try:
        await client.head_bucket(Bucket=MINIO_BUCKET)
    except ClientError as exc:
        status_code = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        if status_code not in {404, 301, 400}:
            raise
        await client.create_bucket(Bucket=MINIO_BUCKET)


async def _put_bytes(path: str, payload: bytes, content_type: str) -> str:
    key = _strip_leading_slash(path)
    session = aioboto3.Session()
    async with session.client("s3", **_client_kwargs()) as client:
        await _ensure_bucket_exists(client)
        await client.put_object(
            Bucket=MINIO_BUCKET,
            Key=key,
            Body=payload,
            ContentType=content_type,
        )
    return f"/{key}"


async def upload_original(
    workspace_id: UUID,
    document_id: UUID,
    file_bytes: bytes,
    filename: str,
) -> str:
    path = original_path(workspace_id, document_id, filename)
    return await _put_bytes(path, file_bytes, "application/pdf")


async def upload_render(
    workspace_id: UUID,
    document_id: UUID,
    page_num: int,
    image_bytes: bytes,
) -> str:
    path = render_path(workspace_id, document_id, page_num)
    return await _put_bytes(path, image_bytes, "image/png")


async def upload_crop(
    workspace_id: UUID,
    document_id: UUID,
    block_id: str,
    image_bytes: bytes,
) -> str:
    path = crop_path(workspace_id, document_id, block_id)
    return await _put_bytes(path, image_bytes, "image/png")


async def upload_ast(
    workspace_id: UUID,
    document_id: UUID,
    parse_run_id: UUID,
    ast_dict: dict[str, object],
) -> str:
    payload = json.dumps(ast_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path = ast_path(workspace_id, document_id, parse_run_id)
    return await _put_bytes(path, payload, "application/json")


async def upload_log(
    workspace_id: UUID,
    document_id: UUID,
    parse_run_id: UUID,
    log_lines: Iterable[str],
) -> str:
    payload = "\n".join(line.rstrip("\n") for line in log_lines).encode("utf-8")
    if payload and not payload.endswith(b"\n"):
        payload += b"\n"
    path = log_path(workspace_id, document_id, parse_run_id)
    return await _put_bytes(path, payload, "application/jsonl")


async def get_object(path: str) -> bytes:
    key = _strip_leading_slash(path)
    session = aioboto3.Session()
    async with session.client("s3", **_client_kwargs()) as client:
        response = await client.get_object(Bucket=MINIO_BUCKET, Key=key)
        async with response["Body"] as body:
            return await body.read()


async def get_signed_url(path: str, expires: int = 3600) -> str:
    key = _strip_leading_slash(path)
    session = aioboto3.Session()
    async with session.client("s3", **_client_kwargs()) as client:
        result = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": MINIO_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
        if inspect.isawaitable(result):
            return await result
        return str(result)
