export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];

export interface JsonObject {
  [key: string]: JsonValue;
}

export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
  coord_space: "page_norm";
}

export interface VerifierComponents {
  ssim: number;
  ocr_consistency: number;
  layout_iou: number;
  clip_sim: number;
}

export interface VerifierScore {
  score: number;
  components: VerifierComponents;
  L_verify: number;
  flag_for_repair: boolean;
}

export interface ConfidenceScore {
  overall: number;
  calibrated: number;
  raw: number;
  uncalibrated?: number | null;
}

export type ParseBlockType =
  | "table"
  | "paragraph"
  | "header"
  | "figure"
  | "equation"
  | "form"
  | "handwriting"
  | "footer";

export interface ParseBlock {
  block_id: string;
  page: number;
  type: ParseBlockType;
  bbox: BBox;
  reading_order_rank: number;
  text: string;
  html: string;
  children: string[];
  source: {
    native_pdf: boolean;
    ocr_engine: string;
    vlm_engine: string;
    verifier: VerifierScore;
    crop_path?: string | null;
    render_path?: string | null;
    layout_confidence?: number | null;
    layout_backend?: string | null;
    layout_backend_version?: string | null;
    warning?: string | null;
    prompt?: string | null;
  };
  confidence: ConfidenceScore;
  citations: Citation[];
}

export interface Citation {
  page: number;
  matching_text: string;
  bboxes: BBox[];
}

export interface FieldMetadata {
  confidence: {
    calibrated: number;
    raw: number;
  };
  citations: Citation[];
  validators: Array<{
    name: string;
    pattern?: string;
    status: string;
  }>;
  warnings: string[];
}

export interface ExtractionResult {
  data: JsonObject;
  field_metadata: Record<string, FieldMetadata>;
}

export type ExtractionRunState = "queued" | "running" | "complete" | "failed";

export interface ParseConfig {
  use_vlm: boolean;
  enable_colpali: boolean;
  document_anchoring: boolean;
  enable_verifier: boolean;
  table_stitching: boolean;
  calibrate_confidence: boolean;
  webhook_url?: string | null;
}

export type ParseRunState =
  | "queued"
  | "running"
  | "intake_complete"
  | "complete"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface UploadFileResponse {
  file_id: string;
  object_path: string;
  sha256: string;
}

export interface ParseRunCreateResponse {
  job_id: string;
  status: ParseRunState;
}

export interface ParseRunStatus {
  id: string;
  status: ParseRunState;
  progress: number;
  cost_credits: number;
  agent_timings_ms: Record<string, number>;
  error: string | null;
}

export interface ParseBlocksResponse {
  run_id: string;
  status: ParseRunState;
  pages_done: number;
  pages_total: number;
  blocks: ParseBlock[];
}

export interface ExtractionRunResponse {
  run_id: string;
  status: ExtractionRunState;
}

export interface ExtractionResultResponse {
  run_id: string;
  status: ExtractionRunState;
  data: JsonObject | null;
  field_metadata: Record<string, FieldMetadata> | null;
  cost_credits?: number | null;
  error?: string | null;
}

export interface RetrievalResult {
  document_id: string;
  page_num: number;
  score: number;
  block_ids: string[];
  bbox?: BBox;
  image_patch_path?: string;
}

export type SchemaFieldType = "string" | "number" | "boolean" | "date";

export interface ExtractionSchemaField {
  id?: string;
  name: string;
  type: SchemaFieldType;
  description: string;
  required: boolean;
}

export interface ExtractionSchemaCreateResponse {
  schema_id: string;
  id?: string;
}

export interface ClassificationCategory {
  id?: string;
  label: string;
  description: string;
  color: string;
}

export interface ClassificationResult {
  page_num: number;
  label: string;
  confidence: number;
  scores: Record<string, number>;
  model?: string;
}

export interface ClassificationRunResponse {
  status: string;
  classifications?: ClassificationResult[];
  results?: ClassificationResult[];
}

export interface SplitSegment {
  start_page: number;
  end_page: number;
  label: string;
  confidence: number;
  evidence?: string;
  semantic_coherence?: number;
}

export interface SplitRunResponse {
  status: string;
  segments?: SplitSegment[];
  result_segments?: SplitSegment[];
}

export interface IndexCollection {
  collection_id: string;
  id?: string;
  name: string;
  page_count: number;
  embedding_model: string;
}

export interface IndexCollectionsResponse {
  collections?: IndexCollection[];
}

export interface IndexCollectionCreateResponse {
  collection_id: string;
  id?: string;
  status: string;
}

export interface IndexSyncResponse {
  status: string;
  pages_to_index?: number;
}
