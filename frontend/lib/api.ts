import type {
  ExtractionResultResponse,
  ExtractionResult,
  ExtractionRunResponse,
  ParseBlocksResponse,
  ParseConfig,
  ParseRunCreateResponse,
  ParseRunStatus,
  RetrievalResult,
  UploadFileResponse
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_DOCUMIND_API_URL ?? "http://localhost:8000";
const DEFAULT_WORKSPACE_ID =
  process.env.NEXT_PUBLIC_DOCUMIND_WORKSPACE_ID ?? "00000000-0000-4000-8000-000000000001";

const defaultParseConfig: ParseConfig = {
  use_vlm: true,
  enable_colpali: true,
  document_anchoring: true,
  enable_verifier: true,
  table_stitching: true,
  calibrate_confidence: true,
  webhook_url: null
};

export async function uploadFile(file: File): Promise<UploadFileResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<UploadFileResponse>("/v1/files", { method: "POST", body: formData });
}

export async function triggerParse(
  fileId: string,
  config: ParseConfig = defaultParseConfig,
): Promise<ParseRunCreateResponse> {
  return request<ParseRunCreateResponse>("/v1/parse/runs", {
    method: "POST",
    body: JSON.stringify({ file_id: fileId, config })
  });
}

export async function pollParseStatus(jobId: string): Promise<ParseRunStatus> {
  return request<ParseRunStatus>(`/v1/parse/runs/${jobId}`, { method: "GET" });
}

export async function getParseBlocks(jobId: string): Promise<ParseBlocksResponse> {
  return request<ParseBlocksResponse>(`/v1/parse/runs/${jobId}/blocks`, { method: "GET" });
}

export async function triggerExtraction(
  parseRunId: string,
  schemaId: string,
): Promise<ExtractionRunResponse> {
  return request<ExtractionRunResponse>("/v1/extract/runs", {
    method: "POST",
    body: JSON.stringify({
      parse_run_id: parseRunId,
      schema_id: schemaId
    })
  });
}

export async function pollExtractionResult(
  runId: string,
  intervalMs = 2000,
  maxAttempts = 60,
): Promise<ExtractionResultResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const result = await request<ExtractionResultResponse>(`/v1/extract/runs/${runId}`, {
      method: "GET"
    });
    if (result.status === "complete" || result.status === "failed") {
      return result;
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, intervalMs);
    });
  }
  throw new Error(`Extraction ${runId} did not complete within timeout`);
}

export async function getExtractionResult(runId: string): Promise<ExtractionResult> {
  const response = await pollExtractionResult(runId);
  return {
    data: response.data ?? {},
    field_metadata: response.field_metadata ?? {}
  };
}

export async function queryIndex(
  collectionId: string,
  query: string,
): Promise<RetrievalResult[]> {
  const response = await request<{ hits: RetrievalResult[] }>("/v1/retrieval/query", {
    method: "POST",
    body: JSON.stringify({ collection_id: collectionId, query })
  });
  return response.hits;
}

export async function getSignedUrl(path: string): Promise<string> {
  const response = await request<{ url: string }>(
    `/v1/artifacts/signed-url?path=${encodeURIComponent(path)}`,
    { method: "GET" },
  );
  return response.url;
}

function getWorkspaceId(): string {
  if (typeof window === "undefined") {
    return DEFAULT_WORKSPACE_ID;
  }
  return window.localStorage.getItem("documind_workspace_id") ?? DEFAULT_WORKSPACE_ID;
}

function getBearerToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem("documind_api_token");
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const token = getBearerToken();
  const headers = new Headers(init.headers);
  headers.set("X-Workspace-Id", getWorkspaceId());
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`DocuMind API ${response.status}: ${detail || response.statusText}`);
  }

  return (await response.json()) as T;
}
