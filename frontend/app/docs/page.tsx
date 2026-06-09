"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { CodeBlock } from "@/components/ui/CodeBlock";

const sections = [
  { id: "overview", label: "Overview" },
  { id: "quick-start", label: "Quick Start" },
  { id: "api-files", label: "POST /v1/files" },
  { id: "api-parse-run", label: "POST /v1/parse/runs" },
  { id: "api-parse-status", label: "GET parse status" },
  { id: "api-parse-blocks", label: "GET parse blocks" },
  { id: "api-extract", label: "Extract API" },
  { id: "api-classify", label: "Classify API" },
  { id: "api-split", label: "Split API" },
  { id: "api-index", label: "Index API" },
  { id: "architecture", label: "Architecture" },
  { id: "configuration", label: "Configuration" },
  { id: "self-hosting", label: "Self-Hosting" }
];

const quickStartCode = `const formData = new FormData()
formData.append('file', file)

const upload = await fetch('/v1/files', {
  method: 'POST',
  headers: { 'X-Workspace-Id': workspaceId },
  body: formData,
})
const { file_id } = await upload.json()

const run = await fetch('/v1/parse/runs', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Workspace-Id': workspaceId,
  },
  body: JSON.stringify({ file_id, config: { enable_verifier: true } }),
})
const { job_id } = await run.json()`;

const dockerCode = `docker-compose -f infra/docker-compose.yml up -d
alembic upgrade head
uvicorn api.main:app --host 0.0.0.0 --port 8000`;

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("overview");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.find((entry) => entry.isIntersecting);
        if (visible?.target.id) {
          setActiveSection(visible.target.id);
        }
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0.01 },
    );
    sections.forEach((section) => {
      const node = document.getElementById(section.id);
      if (node) {
        observer.observe(node);
      }
    });
    return () => observer.disconnect();
  }, []);

  return (
    <div className="min-h-screen p-6">
      <div className="grid gap-6 xl:grid-cols-[220px_minmax(0,1fr)_220px]">
        <DocsNav />
        <main className="max-w-5xl">
          <header className="border-b border-[var(--border)] pb-5">
            <h1 className="text-[28px] font-medium">DocuMind AI Documentation</h1>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
              A seven-agent document parsing and intelligence platform for auditable, cited, calibrated output.
            </p>
          </header>

          <DocSection id="overview" title="Overview">
            <p>
              DocuMind AI is a verifiable document pipeline. It combines parsing, extraction, classification,
              splitting, and visual RAG with confidence calibration, citations, and verifier scores.
            </p>
            <div className="mt-4 overflow-hidden rounded-lg border border-[var(--border)]">
              <table className="w-full border-collapse text-sm">
                <tbody>
                  {[
                    ["Confidence", "ECE-calibrated confidence scores with ECE target below 0.05."],
                    ["Citations", "Bounding-box citations on every extracted field."],
                    ["Verifier", "Render-and-compare checks using SSIM, OCR, CLIP, and IoU."],
                    ["Deployment", "Self-hostable BYOC profiles for parse, extract, and full RAG."],
                    ["Learning", "Correction memory loop for human review and training data."]
                  ].map(([name, text]) => (
                    <tr className="border-t border-[var(--border)] first:border-t-0" key={name}>
                      <td className="w-40 p-3 font-mono text-[var(--brand)]">{name}</td>
                      <td className="p-3 text-[var(--text-secondary)]">{text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DocSection>

          <DocSection id="quick-start" title="Quick Start">
            <ol className="grid gap-2 text-sm text-[var(--text-secondary)]">
              <li>1. Upload a document with <InlineCode>POST /v1/files</InlineCode>.</li>
              <li>2. Trigger parse with <InlineCode>POST /v1/parse/runs</InlineCode>.</li>
              <li>3. Poll <InlineCode>GET /v1/parse/runs/{`{id}`}</InlineCode>.</li>
              <li>4. Fetch blocks with <InlineCode>GET /v1/parse/runs/{`{id}`}/blocks</InlineCode>.</li>
            </ol>
            <div className="mt-4">
              <CodeBlock code={quickStartCode} language="TS" />
            </div>
          </DocSection>

          <DocSection id="api-files" title="POST /v1/files">
            <Endpoint method="POST" path="/v1/files" text="Upload a document for processing." />
            <ParamTable rows={[["file*", "File", "PDF, PNG, JPG, or TIFF binary"], ["filename", "string", "Original filename"]]} />
            <ResponseTable rows={[["file_id", "string", "UUID of uploaded file"], ["object_path", "string", "Workspace-scoped object path"], ["sha256", "string", "SHA-256 hash"]]} />
          </DocSection>

          <DocSection id="api-parse-run" title="POST /v1/parse/runs">
            <Endpoint method="POST" path="/v1/parse/runs" text="Trigger an async parse job. Returns immediately with job_id." />
            <ParamTable
              rows={[
                ["file_id*", "string", "Uploaded file UUID"],
                ["config.use_vlm", "boolean", "Route complex regions to MinerU"],
                ["config.enable_verifier", "boolean", "Run render-and-compare verification"],
                ["config.document_anchoring", "boolean", "Inject native PDF coordinates"],
                ["config.webhook_url", "string", "Optional completion callback"]
              ]}
            />
            <ResponseTable rows={[["job_id", "string", "Parse run UUID"], ["status", "string", "queued, running, complete, or failed"]]} />
          </DocSection>

          <DocSection id="api-parse-status" title="GET /v1/parse/runs/{id}">
            <Endpoint method="GET" path="/v1/parse/runs/{id}" text="Poll parse run status and operational metrics." />
            <ResponseTable
              rows={[
                ["job_id", "string", "Parse run UUID"],
                ["status", "string", "queued | running | complete | failed"],
                ["pages_done", "number", "Completed pages"],
                ["pages_total", "number", "Total pages"],
                ["cost_credits", "number", "Billing or cost accounting"],
                ["started_at", "datetime", "Run start timestamp"],
                ["completed_at", "datetime", "Run completion timestamp"]
              ]}
            />
          </DocSection>

          <DocSection id="api-parse-blocks" title="GET /v1/parse/runs/{id}/blocks">
            <Endpoint method="GET" path="/v1/parse/runs/{id}/blocks" text="Retrieve all ParseBlock records for a completed parse run." />
            <ResponseTable
              rows={[
                ["block_id", "string", "Stable block identifier"],
                ["page", "number", "Zero-indexed page number"],
                ["type", "string", "text, heading, table, figure, formula, or footer"],
                ["bbox", "object", "Normalized x, y, w, h coordinates"],
                ["reading_order_rank", "number", "Logical reading order"],
                ["text", "string", "Extracted block text"],
                ["html", "string", "HTML representation for tables"],
                ["confidence", "object", "calibrated, raw, and overall scores"],
                ["citations", "array", "Page and bbox citations"],
                ["source.verifier", "object", "SSIM, OCR, CLIP, IoU, and L_verify scores"]
              ]}
            />
          </DocSection>

          <DocSection id="api-extract" title="Extract API">
            <Endpoint method="POST" path="/v1/extract/schemas" text="Create an extraction schema." />
            <ParamTable rows={[["name*", "string", "Schema display name"], ["json_schema*", "object", "JSON Schema for fields"]]} />
            <Endpoint method="POST" path="/v1/extract/runs" text="Trigger async extraction for a parse run." />
            <ParamTable rows={[["parse_run_id*", "string", "Completed parse run UUID"], ["schema_id*", "string", "Extraction schema UUID"]]} />
            <Endpoint method="GET" path="/v1/extract/runs/{id}" text="Poll extraction run and retrieve results." />
            <ResponseTable rows={[["data", "object", "Extracted field values"], ["field_metadata", "object", "Confidence, citations, validators, and warnings per field"]]} />
          </DocSection>

          <DocSection id="api-classify" title="POST /v1/classify/runs">
            <Endpoint method="POST" path="/v1/classify/runs" text="Classify pages against a taxonomy." />
            <ParamTable rows={[["parse_run_id*", "string", "Completed parse run UUID"], ["taxonomy*", "array", "Objects with label and description"]]} />
            <ResponseTable rows={[["classifications", "array", "page_num, label, confidence, scores, and model"]]} />
          </DocSection>

          <DocSection id="api-split" title="POST /v1/split/runs">
            <Endpoint method="POST" path="/v1/split/runs" text="Detect semantic segments in concatenated documents." />
            <ParamTable rows={[["parse_run_id*", "string", "Completed parse run UUID"], ["config.min_segment_pages", "number", "Minimum pages per segment"], ["config.similarity_threshold", "number", "Boundary sensitivity"]]} />
            <ResponseTable rows={[["segments", "array", "start_page, end_page, label, confidence, evidence"]]} />
          </DocSection>

          <DocSection id="api-index" title="Index API">
            <Endpoint method="POST" path="/v1/index/collections" text="Create a visual RAG collection." />
            <ParamTable rows={[["name*", "string", "Collection name"], ["embedding_model", "string", "colqwen2 by default"]]} />
            <Endpoint method="POST" path="/v1/index/collections/{id}/sync" text="Add a parse run to a collection." />
            <ParamTable rows={[["parse_run_id*", "string", "Parse run to embed"]]} />
            <Endpoint method="POST" path="/v1/retrieval/query" text="Run MaxSim visual search." />
            <ParamTable rows={[["collection_id*", "string", "Collection UUID"], ["query*", "string", "Natural-language query"], ["limit", "number", "Maximum hits"]]} />
            <ResponseTable rows={[["hits", "array", "document_id, page_num, score, block_ids, bbox, image_patch_path"]]} />
          </DocSection>

          <DocSection id="architecture" title="Architecture">
            <div className="grid gap-3">
              {[
                ["Agent 1", "Intake and Anchoring", "Input raw PDF or image. Output 300 DPI renders and native coordinate spans."],
                ["Agent 2", "Layout Detection and Triage", "Detects text, tables, figures, formulas, headers, and footers. Routes by region complexity."],
                ["Agent 3", "Specialist Parsers", "PaddleOCR-VL for text, MinerU for tables/formulas, olmOCR or Nougat for scans and handwriting."],
                ["Agent 4", "Reading Order Reconstruction", "Weighted DAG ordering: W(i,j)=0.4 spatial + 0.3 semantic + 0.3 column prior."],
                ["Agent 5", "Render-and-Compare Verifier", "L_verify=0.35(1-SSIM)+0.25L_OCR+0.25(1-IoU)+0.15(1-CLIP)."],
                ["Agent 6", "Schema Extraction", "Constrained decoding produces typed JSON with calibrated confidence and bbox citations."],
                ["Agent 7", "Visual RAG Indexing", "ColQwen2 multi-vector patches stored in Qdrant with MaxSim late interaction retrieval."]
              ].map(([label, title, text]) => (
                <Card className="p-4" key={label}>
                  <Badge label={label} status="neutral" />
                  <h3 className="mt-3 text-base font-medium" id={slug(title)}>{title}</h3>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">{text}</p>
                </Card>
              ))}
            </div>
          </DocSection>

          <DocSection id="configuration" title="Configuration">
            <ParamTable
              rows={[
                ["DOCUMINT_PROFILE", "enum", "parse_only | parse_extract | rag_only | full"],
                ["DOCUMINT_JWT_SECRET", "string", "Required signing secret"],
                ["DOCUMINT_DEV_MODE", "boolean", "Enables X-Workspace-Id header auth"],
                ["DOCUMINT_LAYOUT_BACKEND", "enum", "docling | yolov9_triton | heuristic"],
                ["DOCUMINT_MINERU_ENDPOINT", "url", "MinerU server endpoint"],
                ["DOCUMINT_OLMOCR_STUB", "boolean", "Skip olmOCR in development"],
                ["DOCUMINT_OLMOCR_FAIL_CLOSED", "boolean", "Hard fail when olmOCR unavailable"],
                ["DOCUMINT_COLPALI_MODEL", "string", "vidore/colqwen2-v1.0"],
                ["DOCUMINT_MODEL_CACHE_DIR", "path", "Model cache directory"],
                ["DOCUMINT_COLPALI_OFFLINE", "boolean", "Use cached models only"],
                ["DOCUMINT_EXTRACTION_BACKEND", "enum", "anthropic | openai_compat | transformers | deterministic"],
                ["ANTHROPIC_API_KEY", "string", "Anthropic extraction backend key"],
                ["DOCUMINT_EXTRACTION_ENDPOINT", "url", "OpenAI-compatible extraction endpoint"],
                ["DOCUMINT_VERIFIER_PIL_FALLBACK", "boolean", "Allow degraded PIL renderer"],
                ["DATABASE_URL", "url", "postgresql+asyncpg connection string"],
                ["QDRANT_URL", "url", "Qdrant endpoint"]
              ]}
            />
          </DocSection>

          <DocSection id="self-hosting" title="Self-Hosting">
            <div className="grid gap-3 md:grid-cols-3">
              <Profile name="parse_only" text="Agents 1-4. Requires layout and OCR models. Around 4GB RAM." />
              <Profile name="parse_extract" text="Agents 1-6. Adds schema extraction backend. Around 6GB RAM." />
              <Profile name="full" text="All 7 agents. Adds ColQwen2 and Qdrant. Around 14GB RAM or GPU-backed deployment." />
            </div>
            <div className="mt-4">
              <CodeBlock code={dockerCode} language="bash" />
            </div>
          </DocSection>
        </main>
        <aside className="hidden xl:block">
          <Card className="sticky top-6 p-3">
            <p className="px-2 py-2 font-mono text-[11px] uppercase text-[var(--text-muted)]">On this page</p>
            {sections.map((section) => (
              <a
                className={`block rounded-md px-2 py-1.5 text-xs ${
                  activeSection === section.id
                    ? "bg-[var(--surface-3)] text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
                }`}
                href={`#${section.id}`}
                key={section.id}
              >
                {section.label}
              </a>
            ))}
          </Card>
        </aside>
      </div>
      <a className="fixed bottom-5 right-5 grid h-10 w-10 place-items-center rounded-md border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]" href="#overview" title="Back to top">
        <i className="ti ti-arrow-up" />
      </a>
    </div>
  );
}

function DocsNav() {
  return (
    <aside className="lg:sticky lg:top-6 lg:h-[calc(100vh-48px)]">
      <Card className="p-3">
        <p className="px-2 py-2 font-mono text-[11px] uppercase text-[var(--text-muted)]">Docs</p>
        {sections.slice(0, 6).map((section) => (
          <a className="block rounded-md px-2 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]" href={`#${section.id}`} key={section.id}>
            {section.label}
          </a>
        ))}
      </Card>
    </aside>
  );
}

function DocSection({ children, id, title }: { children: React.ReactNode; id: string; title: string }) {
  function copyHash() {
    void navigator.clipboard.writeText(`${window.location.origin}${window.location.pathname}#${id}`);
  }

  return (
    <section className="border-b border-[var(--border)] py-8" id={id}>
      <button className="group inline-flex items-center gap-2 text-left" onClick={copyHash} type="button">
        <h2 className="text-xl font-medium">{title}</h2>
        <span className="font-mono text-xs text-[var(--text-muted)] opacity-0 group-hover:opacity-100">#</span>
      </button>
      <div className="mt-4 text-sm leading-7 text-[var(--text-secondary)]">{children}</div>
    </section>
  );
}

function Endpoint({ method, path, text }: { method: "GET" | "POST" | "DELETE"; path: string; text: string }) {
  const status = method === "GET" ? "success" : method === "POST" ? "info" : "error";
  return (
    <Card className="mt-3 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge label={method} status={status} />
        <span className="font-mono text-sm text-[var(--text-primary)]">{path}</span>
      </div>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">{text}</p>
    </Card>
  );
}

function ParamTable({ rows }: { rows: string[][] }) {
  return <DataTable heading="Parameters" rows={rows} />;
}

function ResponseTable({ rows }: { rows: string[][] }) {
  return <DataTable heading="Response schema" rows={rows} />;
}

function DataTable({ heading, rows }: { heading: string; rows: string[][] }) {
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-[var(--border)]">
      <div className="border-b border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 font-mono text-[11px] uppercase text-[var(--text-muted)]">
        {heading}
      </div>
      <table className="w-full border-collapse text-sm">
        <tbody>
          {rows.map(([name, type, description]) => (
            <tr className="border-t border-[var(--border)] first:border-t-0" key={`${heading}-${name}`}>
              <td className="w-56 p-3 font-mono text-[var(--brand)]">{name}</td>
              <td className="w-32 p-3 font-mono text-[var(--purple)]">{type}</td>
              <td className="p-3 text-[var(--text-secondary)]">{description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-[var(--surface-3)] px-1.5 py-1 font-mono text-[13px] text-[var(--text-primary)]">{children}</code>;
}

function Profile({ name, text }: { name: string; text: string }) {
  return (
    <Card className="p-4">
      <h3 className="font-mono text-sm text-[var(--brand)]">{name}</h3>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">{text}</p>
    </Card>
  );
}

function slug(input: string) {
  return input.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
