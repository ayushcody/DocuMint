"use client";

import { useState } from "react";

import { triggerSplit } from "@/lib/api";
import { getWorkspaceId } from "@/lib/config";
import { useParseStore } from "@/lib/store";
import type { SplitSegment } from "@/lib/types";
import { SegmentBar } from "@/components/ops/SegmentBar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";

export function SplitPanel() {
  const toast = useToast();
  const parseRunIdFromStore = useParseStore((state) => state.parseRunId);
  const [parseRunId, setParseRunId] = useState(parseRunIdFromStore ?? "");
  const [minSegmentPages, setMinSegmentPages] = useState(1);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.35);
  const [segments, setSegments] = useState<SplitSegment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function splitDocument() {
    if (!parseRunId.trim()) {
      setError("Enter a Parse Run ID to detect document segments");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await triggerSplit(parseRunId.trim(), {
        min_segment_pages: minSegmentPages,
        similarity_threshold: similarityThreshold
      });
      setSegments(response.segments ?? response.result_segments ?? []);
      toast.success("Split analysis complete");
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Split failed";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  const totalPages = Math.max(1, ...segments.map((segment) => segment.end_page + 1));

  return (
    <div className="min-h-screen p-6">
      <Header />
      <Card className="mt-5 p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_260px_320px_auto] lg:items-end">
          <label>
            <span className="text-xs text-[var(--text-muted)]">Parse Run ID</span>
            <input
              id="primary-input"
              className="mt-1 h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-3 font-mono text-sm"
              onChange={(event) => setParseRunId(event.target.value)}
              placeholder="Completed parse run"
              value={parseRunId}
            />
          </label>
          <label>
            <span className="flex justify-between text-xs text-[var(--text-muted)]">
              min_segment_pages <span className="font-mono">{minSegmentPages}</span>
            </span>
            <input className="mt-3 w-full accent-[var(--brand)]" max={10} min={1} onChange={(event) => setMinSegmentPages(Number(event.target.value))} type="range" value={minSegmentPages} />
          </label>
          <label>
            <span className="flex justify-between text-xs text-[var(--text-muted)]">
              similarity threshold <span className="font-mono">{similarityThreshold.toFixed(2)}</span>
            </span>
            <input className="mt-3 w-full accent-[var(--brand)]" max={0.9} min={0.1} onChange={(event) => setSimilarityThreshold(Number(event.target.value))} step={0.05} type="range" value={similarityThreshold} />
            <span className="text-[11px] text-[var(--text-muted)]">Lower = fewer splits / Higher = more aggressive splitting</span>
          </label>
          <Button disabled={loading} onClick={splitDocument} variant="primary">
            {loading ? <Spinner /> : null}
            Split Document
          </Button>
        </div>
        {error ? <ErrorBox message={error} /> : null}
      </Card>
      <Card className="mt-5 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium">Visual segment timeline</h2>
          <Badge label={`${segments.length} segments`} status={segments.length ? "info" : "neutral"} />
        </div>
        {loading ? (
          <div className="mt-5">
            <Skeleton height={96} width="100%" borderRadius={8} />
          </div>
        ) : segments.length ? (
          <div className="mt-5">
            <SegmentBar segments={segments} totalPages={totalPages} />
            <div className="mt-2 flex">
              {segments.map((segment) => {
                const pages = segment.end_page - segment.start_page + 1;
                return (
                  <span className="font-mono text-[11px] text-[var(--text-muted)]" key={`${segment.start_page}-label`} style={{ width: `${(pages / totalPages) * 100}%` }}>
                    p{segment.start_page + 1}-{segment.end_page + 1}
                  </span>
                );
              })}
            </div>
          </div>
        ) : (
          <EmptyState />
        )}
      </Card>
      {segments.length ? (
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {segments.map((segment, index) => {
            const pages = segment.end_page - segment.start_page + 1;
            const coherence = segment.semantic_coherence ?? segment.confidence;
            return (
              <Card className="p-4" key={`${segment.start_page}-${segment.end_page}-card`}>
                <div className="flex items-center justify-between">
                  <Badge label={`Segment ${index + 1}`} status="neutral" />
                  <span className="font-mono text-xs text-[var(--text-muted)]">p{segment.start_page + 1}-{segment.end_page + 1}</span>
                </div>
                <h3 className="mt-3 text-lg font-medium">{segment.label}</h3>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">{pages} page{pages === 1 ? "" : "s"}</p>
                <Metric label="Confidence" value={segment.confidence} />
                <Metric label="Semantic coherence" value={coherence} />
                <p className="mt-4 text-sm text-[var(--text-muted)]">{segment.evidence || "No boundary evidence returned"}</p>
              </Card>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function Header() {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] pb-4">
      <div>
        <h1 className="text-2xl font-medium">Split</h1>
        <p className="text-sm text-[var(--text-secondary)]">Detect document boundaries in concatenated packets</p>
      </div>
      <span className="font-mono text-[11px] text-[var(--text-muted)]">ws {getWorkspaceId().slice(0, 8)}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="mt-4">
      <div className="flex justify-between text-xs text-[var(--text-muted)]">
        <span>{label}</span>
        <span className="font-mono">{value.toFixed(2)}</span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-[var(--surface-3)]">
        <div className="h-full rounded bg-[var(--brand)]" style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mt-5 grid min-h-[220px] place-items-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-2)] text-center">
      <div>
        <i className="ti ti-scissors text-3xl text-[var(--text-muted)]" />
        <p className="mt-3 text-sm text-[var(--text-secondary)]">Enter a Parse Run ID to detect document segments</p>
      </div>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <div className="mt-4 rounded-md border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] p-3 text-sm text-[var(--red)]">{message}</div>;
}
