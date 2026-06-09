import type {
  ExtractionResultResponse,
  ExtractionResult,
  ExtractionRunResponse,
  ClassificationCategory,
  ClassificationRunResponse,
  ExtractionSchemaCreateResponse,
  ExtractionSchemaField,
  IndexCollection,
  IndexCollectionCreateResponse,
  IndexCollectionsResponse,
  IndexSyncResponse,
  ParseBlocksResponse,
  ParseConfig,
  ParseRunCreateResponse,
  ParseRunStatus,
  RetrievalResult,
  SplitRunResponse,
  UploadFileResponse
} from "@/lib/types";
import { API_BASE, getBearerToken, getWorkspaceId } from "@/lib/config";

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
  formData.append("filename", file.name);
  return request<UploadFileResponse>("/v1/files", { method: "POST", body: formData });
}

export async function uploadFileWithProgress(
  file: File,
  onProgress: (progress: number) => void,
): Promise<UploadFileResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("filename", file.name);
  const token = getBearerToken();

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as UploadFileResponse);
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.responseText || xhr.statusText}`));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.open("POST", `${API_BASE}/v1/files`);
    xhr.setRequestHeader("X-Workspace-Id", getWorkspaceId());
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.send(formData);
  });
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
  const result = await request<ParseRunStatus & { pages_done?: number; pages_total?: number }>(`/v1/parse/runs/${jobId}`, {
    method: "GET"
  });
  const pagesDone = result.pages_done ?? 0;
  const pagesTotal = result.pages_total ?? 0;
  return {
    ...result,
    progress: result.progress ?? (pagesTotal > 0 ? Math.round((pagesDone / pagesTotal) * 100) : 0)
  };
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

export async function createExtractionSchema(
  name: string,
  fields: ExtractionSchemaField[],
): Promise<ExtractionSchemaCreateResponse> {
  return request<ExtractionSchemaCreateResponse>("/v1/extract/schemas", {
    method: "POST",
    body: JSON.stringify({
      name,
      json_schema: buildJsonSchema(fields)
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

export async function getExtractionRun(runId: string): Promise<ExtractionResultResponse> {
  return request<ExtractionResultResponse>(`/v1/extract/runs/${runId}`, {
    method: "GET"
  });
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
  const response = await request<{ hits?: RetrievalResult[]; results?: RetrievalResult[] }>("/v1/retrieval/query", {
    method: "POST",
    body: JSON.stringify({ collection_id: collectionId, query, limit: 5 })
  });
  return response.hits ?? response.results ?? [];
}

export async function triggerClassification(
  parseRunId: string,
  taxonomy: ClassificationCategory[],
): Promise<ClassificationRunResponse> {
  const response = await request<ClassificationRunResponse>("/v1/classify/runs", {
    method: "POST",
    body: JSON.stringify({
      parse_run_id: parseRunId,
      taxonomy: taxonomy.map(({ description, label }) => ({ description, label }))
    })
  });
  return {
    ...response,
    classifications: response.classifications ?? response.results ?? []
  };
}

export async function triggerSplit(
  parseRunId: string,
  config: { min_segment_pages: number; similarity_threshold: number },
): Promise<SplitRunResponse> {
  const response = await request<SplitRunResponse>("/v1/split/runs", {
    method: "POST",
    body: JSON.stringify({ parse_run_id: parseRunId, config })
  });
  return {
    ...response,
    segments: response.segments ?? response.result_segments ?? []
  };
}

export async function listIndexCollections(): Promise<IndexCollection[]> {
  const response = await request<IndexCollectionsResponse | IndexCollection[]>("/v1/index/collections", {
    method: "GET"
  });
  const collections = Array.isArray(response) ? response : response.collections ?? [];
  return collections.map((collection) => ({
    ...collection,
    collection_id: collection.collection_id ?? collection.id ?? collection.name
  }));
}

export async function createIndexCollection(
  name: string,
  embeddingModel = "colqwen2",
): Promise<IndexCollectionCreateResponse> {
  return request<IndexCollectionCreateResponse>("/v1/index/collections", {
    method: "POST",
    body: JSON.stringify({ name, embedding_model: embeddingModel })
  });
}

export async function syncIndexCollection(
  collectionId: string,
  parseRunId: string,
): Promise<IndexSyncResponse> {
  return request<IndexSyncResponse>(`/v1/index/collections/${collectionId}/sync`, {
    method: "POST",
    body: JSON.stringify({ parse_run_id: parseRunId })
  });
}

export async function getSignedUrl(path: string): Promise<string> {
  const response = await request<{ url: string }>(
    `/v1/artifacts/signed-url?path=${encodeURIComponent(path)}`,
    { method: "GET" },
  );
  return response.url;
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

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`DocuMind API ${response.status}: ${detail || response.statusText}`);
  }

  return (await response.json()) as T;
}

function buildJsonSchema(fields: ExtractionSchemaField[]) {
  return {
    type: "object",
    properties: Object.fromEntries(
      fields
        .filter((field) => field.name.trim())
        .map((field) => [
          field.name.trim(),
          {
            type: field.type === "date" ? "string" : field.type,
            ...(field.type === "date" ? { format: "date" } : {}),
            description: field.description
          }
        ])
    ),
    required: fields.filter((field) => field.required && field.name.trim()).map((field) => field.name.trim())
  };
}
