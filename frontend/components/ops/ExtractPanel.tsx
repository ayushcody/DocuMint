"use client";

import { Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { createExtractionSchema, getExtractionRun, triggerExtraction } from "@/lib/api";
import { getWorkspaceId } from "@/lib/config";
import { useParseStore } from "@/lib/store";
import type { Citation, ExtractionResultResponse, ExtractionSchemaField, SchemaFieldType } from "@/lib/types";
import { CitationInspector } from "@/components/CitationInspector";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/Card";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Spinner } from "@/components/ui/Spinner";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";

const typeOptions: SchemaFieldType[] = ["string", "number", "boolean", "date"];

export function ExtractPanel() {
  const toast = useToast();
  const parseRunIdFromStore = useParseStore((state) => state.parseRunId);
  const pdfUrl = useParseStore((state) => state.pdfUrl);
  const setExtractionResult = useParseStore((state) => state.setExtractionResult);
  const [schemaName, setSchemaName] = useState("invoice_core");
  const [fields, setFields] = useState<ExtractionSchemaField[]>([
    { id: "invoice_number", name: "invoice_number", type: "string", description: "Unique invoice identifier", required: true },
    { id: "total_due", name: "total_due", type: "number", description: "Final amount due", required: true }
  ]);
  const [parseRunId, setParseRunId] = useState(parseRunIdFromStore ?? "");
  const [schemaId, setSchemaId] = useState<string | null>(null);
  const [extractRunId, setExtractRunId] = useState<string | null>(null);
  const [extractStatus, setExtractStatus] = useState<"idle" | "queued" | "running" | "complete" | "failed">("idle");
  const [extractResult, setExtractResult] = useState<ExtractionResultResponse | null>(null);
  const [triggerMs, setTriggerMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const pollRef = useRef<number | null>(null);

  const schemaPreview = useMemo(() => buildSchema(fields), [fields]);
  const loading = extractStatus === "queued" || extractStatus === "running";

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
    };
  }, []);

  async function runExtraction() {
    if (!parseRunId.trim()) {
      setError("Paste a Parse Run ID before extracting fields");
      return;
    }
    setExtractStatus("queued");
    setError(null);
    try {
      let nextSchemaId = schemaId;
      if (!nextSchemaId) {
        const schema = await createExtractionSchema(schemaName, fields);
        nextSchemaId = schema.schema_id ?? schema.id ?? null;
        setSchemaId(nextSchemaId);
      }
      if (!nextSchemaId) {
        throw new Error("Schema creation did not return a schema id");
      }
      const t0 = Date.now();
      const run = await triggerExtraction(parseRunId.trim(), nextSchemaId);
      const latency = Date.now() - t0;
      setTriggerMs(latency);
      setExtractRunId(run.run_id);
      setExtractStatus(run.status ?? "queued");
      toast[latency < 500 ? "success" : "warning"](
        latency < 500 ? `Extraction queued in ${latency}ms` : `Extraction trigger took ${latency}ms`,
      );
      startPolling(run.run_id);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Extraction failed";
      setExtractStatus("failed");
      setError(message);
      toast.error(message);
    }
  }

  function startPolling(runId: string) {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
    }
    pollRef.current = window.setInterval(() => {
      void getExtractionRun(runId)
        .then((response) => {
          setExtractStatus(response.status);
          if (response.status === "complete" || response.status === "failed") {
            if (pollRef.current) {
              window.clearInterval(pollRef.current);
            }
            setExtractResult(response);
            if (response.status === "complete") {
              setExtractionResult({
                data: response.data ?? {},
                field_metadata: response.field_metadata ?? {}
              });
              toast.success("Extraction complete");
            } else {
              toast.error(response.error ?? "Extraction failed");
            }
          }
        })
        .catch((nextError: unknown) => {
          const message = nextError instanceof Error ? nextError.message : "Extraction polling failed";
          setError(message);
          toast.error(message);
        });
    }, 2000);
  }

  return (
    <div className="min-h-screen p-6">
      <Header />
      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(440px,0.48fr)_minmax(0,0.52fr)]">
        <Card className="p-5">
          <SectionTitle kicker="Schema builder" title="Define the extraction contract" />
          <label className="mt-4 block">
            <span className="text-xs text-[var(--text-muted)]">Schema name</span>
            <input
              id="primary-input"
              className="mt-1 h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-3 font-mono text-sm text-[var(--text-primary)]"
              onChange={(event) => setSchemaName(event.target.value)}
              value={schemaName}
            />
          </label>
          <div className="mt-5 grid gap-2">
            {fields.map((field, index) => (
              <FieldRow
                field={field}
                key={`${field.name}-${index}`}
                onChange={(nextField) => setFields((current) => current.map((item, itemIndex) => (itemIndex === index ? nextField : item)))}
                onDelete={() => setFields((current) => current.filter((_, itemIndex) => itemIndex !== index))}
              />
            ))}
          </div>
          <Button
            className="mt-3"
            icon={<Plus size={15} />}
            onClick={() => setFields((current) => [...current, { id: crypto.randomUUID(), name: "", type: "string", description: "", required: false }])}
          >
            Add Field
          </Button>
          <div className="mt-5">
            <SectionTitle kicker="Preview" title="JSON Schema" />
            <div className="mt-3">
              <CodeBlock code={JSON.stringify(schemaPreview, null, 2)} language="JSON" maxHeight={260} />
            </div>
          </div>
          <label className="mt-5 block">
            <span className="text-xs text-[var(--text-muted)]">Parse Run ID</span>
            <input
              className="mt-1 h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-3 font-mono text-sm text-[var(--text-primary)]"
              onChange={(event) => setParseRunId(event.target.value)}
              placeholder="Paste completed parse run id"
              value={parseRunId}
            />
          </label>
          <Button className="mt-4 w-full" disabled={loading} onClick={runExtraction} variant="primary">
            {loading ? <Spinner /> : null}
            Extract Fields
          </Button>
          {extractRunId ? (
            <p className="mt-3 font-mono text-xs text-[var(--text-muted)]">
              run {extractRunId.slice(0, 12)} - {extractStatus}
              {triggerMs !== null ? (
                <span className={triggerMs < 500 ? "ml-2 text-[var(--green)]" : "ml-2 text-[var(--amber)]"}>
                  {triggerMs < 500 ? `queued in ${triggerMs}ms ✓` : `triggered in ${triggerMs}ms`}
                </span>
              ) : null}
            </p>
          ) : null}
          {error ? <ErrorBox message={error} /> : null}
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <SectionTitle kicker="Extraction results" title="Cited field output" />
            <Badge label="constrained decoding" status="ai" />
          </div>
          <div className="mt-5">
            {loading ? (
              <SkeletonGrid count={fields.length} />
            ) : extractResult ? (
              <div className="grid gap-3 md:grid-cols-2">
                {Object.entries(extractResult.data ?? {}).map(([name, value]) => {
                  const metadata = extractResult.field_metadata?.[name];
                  const confidence = metadata?.confidence.calibrated ?? 0;
                  return (
                    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4" key={name}>
                      <div className="flex items-start justify-between gap-3">
                        <span className="font-mono text-sm text-[var(--brand)]">{name}</span>
                        <Badge
                          label={confidence.toFixed(2)}
                          status={confidence >= 0.85 ? "success" : confidence >= 0.7 ? "warning" : "error"}
                        />
                      </div>
                      <p className="mt-3 break-words text-xl font-medium text-[var(--text-primary)]">{String(value)}</p>
                      <Badge className="mt-3" label={triggerMs !== null && triggerMs > 500 ? "deterministic" : "constrained"} status={triggerMs !== null && triggerMs > 500 ? "warning" : "ai"} />
                      <div className="mt-4 flex flex-wrap gap-2">
                        {metadata?.validators.map((validator) => (
                          <Badge
                            key={`${validator.name}-${validator.status}`}
                            label={`${validator.name} ${validator.status}`}
                            status={validator.status.toLowerCase() === "pass" ? "success" : "error"}
                          />
                        ))}
                        {metadata?.warnings.map((warning) => <Badge key={warning} label={warning} status="warning" />)}
                      </div>
                      <Button
                        className="mt-4"
                        disabled={!metadata?.citations?.length}
                        onClick={() => setActiveCitation(metadata?.citations[0] ?? null)}
                        variant="ghost"
                      >
                        View Citation
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState />
            )}
          </div>
        </Card>
      </div>
      {activeCitation ? (
        <div className="fixed inset-0 z-40 bg-[rgba(0,0,0,0.72)] p-4">
          <button
            aria-label="Close citation"
            className="absolute right-5 top-5 z-50 grid h-9 w-9 place-items-center rounded-md bg-[var(--surface-3)] text-[var(--text-primary)]"
            onClick={() => setActiveCitation(null)}
            type="button"
          >
            <X size={16} />
          </button>
          <CitationInspector citation={activeCitation} onClose={() => setActiveCitation(null)} pdfUrl={pdfUrl} />
        </div>
      ) : null}
    </div>
  );
}

function Header() {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] pb-4">
      <div>
        <h1 className="text-2xl font-medium">Extract</h1>
        <p className="text-sm text-[var(--text-secondary)]">Define schemas and extract cited fields from completed parse runs</p>
      </div>
      <span className="font-mono text-[11px] text-[var(--text-muted)]">ws {getWorkspaceId().slice(0, 8)}</span>
    </div>
  );
}

function FieldRow({
  field,
  onChange,
  onDelete
}: {
  field: ExtractionSchemaField;
  onChange: (field: ExtractionSchemaField) => void;
  onDelete: () => void;
}) {
  return (
    <div className="grid gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3 lg:grid-cols-[1fr_120px_1.3fr_90px_36px]">
      <input
        className="h-9 rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-2 font-mono text-sm"
        onChange={(event) => onChange({ ...field, name: event.target.value })}
        placeholder="field_name"
        value={field.name}
      />
      <select
        className="h-9 rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-2 text-sm"
        onChange={(event) => onChange({ ...field, type: event.target.value as SchemaFieldType })}
        value={field.type}
      >
        {typeOptions.map((type) => <option key={type}>{type}</option>)}
      </select>
      <label>
        <input
          className="h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-2 text-sm"
          onChange={(event) => onChange({ ...field, description: event.target.value })}
          placeholder="Description"
          value={field.description}
        />
        <span className="mt-1 block text-right font-mono text-[10px] text-[var(--text-muted)]">{field.description.length} chars</span>
      </label>
      <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
        <input checked={field.required} className="accent-[var(--brand)]" onChange={(event) => onChange({ ...field, required: event.target.checked })} type="checkbox" />
        Required
      </label>
      <Button aria-label="Delete field" className="h-9 w-9 px-0" icon={<Trash2 size={14} />} onClick={onDelete} variant="ghost" />
    </div>
  );
}

function SectionTitle({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div>
      <p className="font-mono text-[11px] uppercase text-[var(--text-muted)]">{kicker}</p>
      <h2 className="mt-1 text-base font-medium">{title}</h2>
    </div>
  );
}

function SkeletonGrid({ count }: { count: number }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {Array.from({ length: Math.max(2, count) }).map((_, index) => (
        <Skeleton height={160} width="100%" borderRadius={8} key={index} />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="grid min-h-[420px] place-items-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-2)] text-center">
      <div>
        <i className="ti ti-braces text-3xl text-[var(--text-muted)]" />
        <p className="mt-3 text-sm text-[var(--text-secondary)]">Run a parse first, then define your extraction schema</p>
      </div>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <div className="mt-4 rounded-md border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] p-3 text-sm text-[var(--red)]">{message}</div>;
}

function buildSchema(fields: ExtractionSchemaField[]) {
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
