"use client";

import type { ReactNode } from "react";
import {
  Activity,
  BadgeCheck,
  Eye,
  FileUp,
  Gauge,
  PanelRight,
  Play,
  SearchCode,
  ShieldCheck,
  Sparkles,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import { useMemo, useState } from "react";

import { CitationInspector } from "@/components/CitationInspector";
import { ConfidenceHeatmap, HeatmapLegend } from "@/components/ConfidenceHeatmap";
import { PDFViewer } from "@/components/PDFViewer";
import { ReviewQueue } from "@/components/ReviewQueue";
import { SchemaBuilder } from "@/components/SchemaBuilder";
import { Button } from "@/components/ui/button";
import { ConfidencePill } from "@/components/ui/confidence-pill";
import { getParseBlocks, pollParseStatus, triggerParse, uploadFile } from "@/lib/api";
import { useParseStore } from "@/lib/store";
import type { Citation, ParseBlock } from "@/lib/types";
import { AstEditor } from "./AstEditor";
import { MarkdownEditor } from "./MarkdownEditor";
import { PipelineLog } from "./PipelineLog";

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 120;

export function ParseDebugger() {
  const [activeEditor, setActiveEditor] = useState<"ast" | "markdown">("ast");
  const [citation, setCitation] = useState<Citation | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const blocks = useParseStore((state) => state.parseBlocks);
  const pdfFile = useParseStore((state) => state.pdfFile);
  const pdfUrl = useParseStore((state) => state.pdfUrl);
  const parseRunId = useParseStore((state) => state.parseRunId);
  const parseStatus = useParseStore((state) => state.parseStatus);
  const errorMessage = useParseStore((state) => state.errorMessage);
  const selectedBlockId = useParseStore((state) => state.selectedBlockId);
  const zoomLevel = useParseStore((state) => state.zoomLevel);
  const setZoomLevel = useParseStore((state) => state.setZoomLevel);
  const setPdfFile = useParseStore((state) => state.setPdfFile);
  const setParseBlocks = useParseStore((state) => state.setParseBlocks);
  const setExtractionResult = useParseStore((state) => state.setExtractionResult);
  const setParseRunId = useParseStore((state) => state.setParseRunId);
  const setParseStatus = useParseStore((state) => state.setParseStatus);
  const setErrorMessage = useParseStore((state) => state.setErrorMessage);

  const selectedBlock = useMemo(
    () => blocks.find((block) => block.block_id === selectedBlockId) ?? blocks[0] ?? null,
    [blocks, selectedBlockId],
  );
  const flaggedBlocks = blocks.filter((block) => block.source.verifier.flag_for_repair).length;
  const averageConfidence =
    blocks.length > 0
      ? blocks.reduce((total, block) => total + block.confidence.calibrated, 0) / blocks.length
      : 0;

  function handleFileChange(file: File | null) {
    if (!file) {
      return;
    }
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
    }
    setPdfFile(file, URL.createObjectURL(file));
    setParseBlocks([]);
    setExtractionResult(null);
    setParseRunId(null);
    setParseStatus(null);
    setErrorMessage(null);
  }

  async function runParse() {
    if (!pdfFile || isRunning) {
      return;
    }
    setIsRunning(true);
    setErrorMessage(null);

    try {
      const upload = await uploadFile(pdfFile);
      const run = await triggerParse(upload.file_id);
      setParseRunId(run.job_id);
      await refreshBlocks(run.job_id);

      for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
        const status = await pollParseStatus(run.job_id);
        setParseStatus(status);
        await refreshBlocks(run.job_id);
        if (["succeeded", "failed", "cancelled"].includes(status.status)) {
          if (status.status === "failed") {
            throw new Error(status.error ?? "Parse failed");
          }
          break;
        }
        await delay(POLL_INTERVAL_MS);
      }
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to run parse");
    } finally {
      setIsRunning(false);
    }
  }

  async function refreshBlocks(runId: string) {
    const response = await getParseBlocks(runId);
    if (response.blocks.length > 0) {
      setParseBlocks(response.blocks);
    }
  }

  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden bg-paper text-ink lg:h-screen">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-r from-[#cef7f0] via-[#fff1d6] to-[#e9e7ff] opacity-80" />
      <header className="tool-surface relative z-10 m-3 rounded-lg px-4 py-3 shadow-dock">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-ink text-white shadow-glow">
              <Sparkles aria-hidden size={20} />
            </div>
            <div className="min-w-0">
              <h1 className="display-font truncate text-xl font-black tracking-normal md:text-2xl">
                DocuMind Parse Studio
              </h1>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="rounded-md border border-line bg-white px-2 py-1 text-xs font-bold text-muted">
                  {parseRunId ?? "no_parse_run"}
                </span>
                <span className="rounded-md bg-[#edf5ff] px-2 py-1 text-xs font-bold text-sky">
                  {parseStatus?.status ?? "idle"}
                </span>
                <HeatmapLegend />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-semibold shadow-sm transition hover:-translate-y-0.5 hover:border-[#b7c8ce]">
              <FileUp aria-hidden className="text-sky" size={16} />
              {pdfFile?.name ?? "Upload"}
              <input
                accept="application/pdf"
                className="sr-only"
                onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <Button disabled={!pdfFile || isRunning} icon={<Play size={16} />} onClick={runParse} variant="primary">
              {isRunning ? "Running" : "Run Parse"}
            </Button>
            <ConfidenceHeatmap />
            <div className="inline-flex h-9 items-center overflow-hidden rounded-md border border-line bg-white shadow-sm">
              <Button
                aria-label="Zoom out"
                className="h-9 rounded-none border-0"
                icon={<ZoomOut size={16} />}
                onClick={() => setZoomLevel(Math.max(0.7, Number((zoomLevel - 0.1).toFixed(2))))}
                variant="ghost"
              />
              <span className="min-w-14 border-x border-line px-2 text-center text-sm font-black">
                {Math.round(zoomLevel * 100)}%
              </span>
              <Button
                aria-label="Zoom in"
                className="h-9 rounded-none border-0"
                icon={<ZoomIn size={16} />}
                onClick={() => setZoomLevel(Math.min(1.5, Number((zoomLevel + 0.1).toFixed(2))))}
                variant="ghost"
              />
            </div>
          </div>
        </div>

        {errorMessage ? (
          <div className="mt-3 rounded-lg border border-coral/40 bg-[#fff8f8] px-3 py-2 text-sm font-semibold text-coral">
            {errorMessage}
          </div>
        ) : null}

        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          <MetricTile icon={<BadgeCheck size={16} />} label="Blocks" tone="teal" value={String(blocks.length)} />
          <MetricTile
            icon={<Gauge size={16} />}
            label="Avg Confidence"
            tone="sky"
            value={blocks.length > 0 ? averageConfidence.toFixed(2) : "--"}
          />
          <MetricTile icon={<Activity size={16} />} label="Review" tone="coral" value={String(flaggedBlocks)} />
          <MetricTile
            icon={<ShieldCheck size={16} />}
            label="Verifier"
            tone="amber"
            value={parseStatus?.status === "succeeded" ? "done" : "on"}
          />
        </div>
      </header>

      <div className="relative z-10 grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-auto px-3 pb-3 lg:grid-cols-[minmax(360px,1.08fr)_minmax(360px,0.92fr)] lg:overflow-hidden">
        <section className="tool-surface flex min-h-[620px] flex-col overflow-hidden rounded-lg shadow-dock lg:min-h-0">
          <div className="flex min-h-12 items-center justify-between gap-3 border-b border-line bg-white/80 px-3">
            <div className="flex min-w-0 items-center gap-2">
              <Eye aria-hidden className="text-teal" size={17} />
              <span className="truncate text-sm font-black">PDF Canvas</span>
              <span className="hidden rounded-md bg-[#e8faf7] px-2 py-1 text-xs font-bold text-teal sm:inline-flex">
                {selectedBlock?.type ?? "waiting"}
              </span>
            </div>
            {selectedBlock ? (
              <ConfidencePill
                calibrated={selectedBlock.confidence.calibrated}
                raw={selectedBlock.confidence.raw}
              />
            ) : null}
          </div>
          <PDFViewer blocks={blocks} fileUrl={pdfUrl} />
          <PipelineLog timings={parseStatus?.agent_timings_ms ?? {}} />
        </section>

        <section className="grid min-h-[720px] grid-rows-[minmax(420px,1fr)_auto] overflow-hidden rounded-lg lg:min-h-0 lg:grid-rows-[1fr_240px]">
          <div className="flex min-h-0 flex-col">
            <div className="tool-surface flex min-h-12 items-center justify-between gap-2 rounded-t-lg border-b border-line px-3 shadow-sm">
              <div className="inline-flex rounded-md border border-line bg-white p-1 shadow-sm">
                <Button
                  className={activeEditor === "ast" ? "bg-[#e8faf7] text-teal" : ""}
                  icon={<SearchCode size={16} />}
                  onClick={() => setActiveEditor("ast")}
                  variant="ghost"
                >
                  AST
                </Button>
                <Button
                  className={activeEditor === "markdown" ? "bg-[#fff7e8] text-[#9d5b03]" : ""}
                  onClick={() => setActiveEditor("markdown")}
                  variant="ghost"
                >
                  Markdown
                </Button>
              </div>
              <div className="hidden min-w-0 items-center gap-2 text-xs font-bold text-muted sm:flex">
                <PanelRight aria-hidden size={15} />
                <span className="truncate">{selectedBlock?.block_id ?? "no block selected"}</span>
              </div>
            </div>
            <div className="tool-surface min-h-0 flex-1 overflow-hidden rounded-b-lg border-t-0">
              {activeEditor === "ast" ? <AstEditor blocks={blocks} /> : <MarkdownEditor blocks={blocks} />}
            </div>
          </div>

          <aside className="grid min-h-0 grid-cols-1 gap-3 pt-3 xl:grid-cols-2">
            <ExtractionPanel onOpenCitation={setCitation} />
            <div className="tool-surface soft-scrollbar min-h-0 overflow-auto rounded-lg shadow-dock">
              <SchemaBuilder />
              <ReviewQueue blocks={blocks} />
            </div>
          </aside>
        </section>
      </div>
      <CitationInspector citation={citation} onClose={() => setCitation(null)} pdfUrl={pdfUrl} />
    </main>
  );
}

interface MetricTileProps {
  icon: ReactNode;
  label: string;
  tone: "teal" | "sky" | "coral" | "amber";
  value: string;
}

function MetricTile({ icon, label, tone, value }: MetricTileProps) {
  const toneClass = {
    teal: "bg-[#e8faf7] text-teal",
    sky: "bg-[#edf5ff] text-sky",
    coral: "bg-[#fff0f1] text-coral",
    amber: "bg-[#fff7e8] text-[#9d5b03]"
  }[tone];

  return (
    <div className="flex min-w-0 items-center gap-2 rounded-lg border border-line bg-white/90 px-3 py-2 shadow-sm">
      <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-md ${toneClass}`}>{icon}</div>
      <div className="min-w-0">
        <div className="truncate text-xs font-bold text-muted">{label}</div>
        <div className="display-font truncate text-lg font-black leading-tight">{value}</div>
      </div>
    </div>
  );
}

interface ExtractionPanelProps {
  onOpenCitation: (citation: Citation) => void;
}

function ExtractionPanel({ onOpenCitation }: ExtractionPanelProps) {
  const extractionResult = useParseStore((state) => state.extractionResult);
  const fields = extractionResult ? Object.entries(extractionResult.field_metadata) : [];

  return (
    <section className="tool-surface soft-scrollbar min-h-0 overflow-auto rounded-lg p-3 shadow-dock">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-black">Extraction</h2>
        <span className="rounded-md bg-[#edf5ff] px-2 py-1 text-xs font-bold text-sky">
          {fields.length} fields
        </span>
      </div>
      {fields.length === 0 ? (
        <p className="rounded-md border border-line bg-[#f8fbfc] p-3 text-sm font-semibold text-muted">
          Run extraction to inspect field citations.
        </p>
      ) : (
        <div className="grid gap-2">
          {fields.map(([field, metadata]) => {
            const citation = metadata.citations[0] ?? null;
            return (
              <div
                key={field}
                className="rounded-lg border border-line bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:border-[#b7c8ce]"
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-black">{field}</span>
                  <ConfidencePill calibrated={metadata.confidence.calibrated} raw={metadata.confidence.raw} />
                </div>
                <div className="mb-2 truncate text-sm text-muted">
                  {String(extractionResult?.data[field] ?? "")}
                </div>
                <Button disabled={!citation} onClick={() => citation && onOpenCitation(citation)} variant="sunny">
                  View Citation
                </Button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
