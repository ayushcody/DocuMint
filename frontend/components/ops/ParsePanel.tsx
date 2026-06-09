"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { getParseBlocks, pollParseStatus, triggerParse, uploadFileWithProgress } from "@/lib/api";
import { getWorkspaceId } from "@/lib/config";
import { useParseStore } from "@/lib/store";
import type { ParseBlock, ParseConfig, ParseRunState } from "@/lib/types";
import { BlockCard } from "@/components/ops/BlockCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/Card";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { FileDropzone } from "@/components/ui/FileDropzone";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Spinner } from "@/components/ui/Spinner";
import { StatusDot } from "@/components/ui/StatusDot";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";

const stages = ["Intake", "Layout", "Specialists", "Assembly", "Verifier"];

type ParseTab = "blocks" | "markdown" | "json";

const initialConfig: ParseConfig = {
  use_vlm: false,
  enable_colpali: true,
  document_anchoring: true,
  enable_verifier: true,
  table_stitching: true,
  calibrate_confidence: true,
  webhook_url: null
};

export function ParsePanel() {
  const toast = useToast();
  const parseBlocks = useParseStore((state) => state.parseBlocks);
  const selectedBlockId = useParseStore((state) => state.selectedBlockId);
  const setParseBlocks = useParseStore((state) => state.setParseBlocks);
  const setSelectedBlockId = useParseStore((state) => state.setSelectedBlockId);
  const setPdfFile = useParseStore((state) => state.setPdfFile);
  const setParseRunId = useParseStore((state) => state.setParseRunId);
  const setParseStatus = useParseStore((state) => state.setParseStatus);
  const [file, setFile] = useState<File | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<ParseRunState | "idle">("idle");
  const [progress, setProgress] = useState(0);
  const [config, setConfig] = useState<ParseConfig>(initialConfig);
  const [activeTab, setActiveTab] = useState<ParseTab>("blocks");
  const [error, setError] = useState<string | null>(null);
  const [blocksLoading, setBlocksLoading] = useState(false);
  const [agentStages, setAgentStages] = useState(
    stages.map((name) => ({ name, status: "pending" as "pending" | "running" | "complete" | "failed", elapsed: null as string | null })),
  );
  const startTimeRef = useRef<number | null>(null);
  const pollRef = useRef<number | null>(null);

  const markdown = useMemo(() => parseBlocks.map((block) => block.text).filter(Boolean).join("\n\n"), [parseBlocks]);
  const complete = status === "succeeded" || status === "complete";
  const running = status === "queued" || status === "running" || status === "intake_complete";
  const currentStage = Math.min(stages.length - 1, Math.floor((progress / 100) * stages.length));

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
    };
  }, []);

  async function runParse() {
    if (!file) {
      setError("Upload a document before starting parse");
      return;
    }
    setError(null);
    setStatus("queued");
    setProgress(0);
    try {
      const uploaded = fileId ? { file_id: fileId } : await uploadFileWithProgress(file, setUploadProgress);
      setFileId(uploaded.file_id);
      toast.success("Upload complete");
      startTimeRef.current = Date.now();
      setAgentStages(stages.map((name, index) => ({ name, status: index === 0 ? "running" : "pending", elapsed: null })));
      const run = await triggerParse(uploaded.file_id, config);
      setJobId(run.job_id);
      setParseRunId(run.job_id);
      setStatus(run.status);
      startPolling(run.job_id);
    } catch (nextError) {
      setStatus("failed");
      const message = readError(nextError);
      setError(message);
      toast.error(message);
    }
  }

  function startPolling(id: string) {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
    }
    pollRef.current = window.setInterval(() => {
      void pollParseStatus(id)
        .then(async (nextStatus) => {
          const nextProgress = nextStatus.progress ?? 0;
          setStatus(nextStatus.status);
          setProgress(nextProgress);
          setParseStatus(nextStatus);
          updateStages(nextProgress, nextStatus.status);
          if (nextStatus.status === "succeeded" || nextStatus.status === "complete") {
            if (pollRef.current) {
              window.clearInterval(pollRef.current);
            }
            setBlocksLoading(true);
            const response = await getParseBlocks(id);
            setParseBlocks(response.blocks ?? []);
            setBlocksLoading(false);
            toast.success("Parse complete");
          }
          if (nextStatus.status === "failed") {
            if (pollRef.current) {
              window.clearInterval(pollRef.current);
            }
            const message = nextStatus.error ?? "Parse failed";
            setError(message);
            toast.error(message);
          }
        })
        .catch((nextError: unknown) => {
          const message = readError(nextError);
          setError(message);
          toast.error(message);
        });
    }, 3000);
  }

  function updateStages(nextProgress: number, nextStatus: ParseRunState) {
    const completed = nextStatus === "succeeded" || nextStatus === "complete";
    const failed = nextStatus === "failed";
    const stageIndex = completed ? stages.length : Math.min(Math.floor((nextProgress / 100) * stages.length), stages.length - 1);
    const elapsed = startTimeRef.current ? `${((Date.now() - startTimeRef.current) / 1000 / 5).toFixed(1)}s` : null;
    setAgentStages((current) =>
      current.map((stage, index) => ({
        ...stage,
        status: failed && index === stageIndex ? "failed" : index < stageIndex || completed ? "complete" : index === stageIndex ? "running" : "pending",
        elapsed: index < stageIndex || completed ? elapsed : null
      })),
    );
  }

  function handleFile(nextFile: File) {
    const url = URL.createObjectURL(nextFile);
    setFile(nextFile);
    setFileName(nextFile.name);
    setFileSize(nextFile.size);
    setUploadProgress(0);
    setFileId(null);
    setPdfFile(nextFile, url);
    setParseBlocks([]);
    setSelectedBlockId(null);
  }

  return (
    <div className="min-h-screen p-6">
      <Header complete={complete} running={running} />
      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,0.6fr)_minmax(360px,0.4fr)]">
        <Card className="p-5">
          <SectionTitle kicker="Document input" title="Source and parse configuration" />
          <div className="mt-4">
            <FileDropzone accept="image/*,application/pdf" onFile={handleFile} />
          </div>
          {fileName ? (
            <div className="mt-3 rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
              <div className="flex items-center justify-between gap-3 font-mono text-xs">
                <span className="truncate text-[var(--text-secondary)]">{fileName}</span>
                <span className="text-[var(--text-muted)]">{(fileSize / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              <div className="mt-2 h-1.5 rounded bg-[var(--surface-3)]">
                <div className="h-full rounded bg-[var(--brand)] transition-[width]" style={{ width: `${uploadProgress}%` }} />
              </div>
              <p className="mt-1 text-right font-mono text-[11px] text-[var(--text-muted)]">{uploadProgress}% uploaded</p>
            </div>
          ) : null}
          <div className="mt-5 grid gap-3">
            <ConfigToggle
              checked={config.document_anchoring}
              label="document_anchoring"
              onChange={(checked) => setConfig((current) => ({ ...current, document_anchoring: checked }))}
              tip="Inject native PDF coordinates into VLM prompts"
            />
            <ConfigToggle
              checked={config.enable_verifier}
              label="enable_verifier"
              onChange={(checked) => setConfig((current) => ({ ...current, enable_verifier: checked }))}
              tip="Render-and-compare verification on every block"
            />
            <ConfigToggle
              checked={config.use_vlm}
              label="use_vlm"
              onChange={(checked) => setConfig((current) => ({ ...current, use_vlm: checked }))}
              tip="Route complex regions to MinerU2.5-Pro"
            />
          </div>
          <Button className="mt-5 w-full" disabled={running} onClick={runParse} variant="primary">
            {running ? <Spinner /> : null}
            Parse Document
          </Button>
          {error ? (
            <div className="mt-4 rounded-md border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] p-3 text-sm text-[var(--red)]">
              {error}
            </div>
          ) : null}
          <div className="mt-6">
            <ProgressBar currentStage={currentStage} stages={stages} status={status === "failed" ? "failed" : complete ? "complete" : "running"} />
            <div className="mt-5 grid gap-2">
              {agentStages.map((stage) => (
                <div className="flex items-center justify-between rounded-md bg-[var(--surface-2)] px-3 py-2" key={stage.name}>
                  <span className="flex items-center gap-2 text-sm">
                    <StatusDot status={stage.status === "complete" ? "success" : stage.status === "running" ? "running" : stage.status === "failed" ? "error" : "neutral"} />
                    {stage.name}
                  </span>
                  <span className="font-mono text-xs text-[var(--text-muted)]">{stage.elapsed ?? "--"}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
        <Card className="min-h-[640px] p-5">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle kicker="Results" title={jobId ? `Run ${jobId.slice(0, 8)}` : "Parse output"} />
            <Badge label={`${parseBlocks.length} blocks`} status={parseBlocks.length ? "info" : "neutral"} />
          </div>
          <div className="mt-4 flex rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-1">
            {[
              ["blocks", "Blocks"],
              ["markdown", "Markdown"],
              ["json", "JSON AST"]
            ].map(([id, label]) => (
              <button
                className={`h-8 flex-1 rounded text-sm ${activeTab === id ? "bg-[var(--surface-3)] text-[var(--text-primary)]" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"}`}
                key={id}
                onClick={() => setActiveTab(id as ParseTab)}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
          <div className="mt-4">
            {blocksLoading ? (
              <div className="grid gap-3">
                <Skeleton height={80} width="100%" borderRadius={8} />
                <Skeleton height={80} width="100%" borderRadius={8} />
                <Skeleton height={80} width="100%" borderRadius={8} />
              </div>
            ) : parseBlocks.length === 0 ? (
              <EmptyState icon="ti-file-upload" text="Upload a document to begin parsing" />
            ) : activeTab === "blocks" ? (
              <div className="grid gap-3">
                {parseBlocks.map((block) => (
                  <BlockCard
                    block={block}
                    isSelected={selectedBlockId === block.block_id}
                    key={block.block_id}
                    onClick={() => setSelectedBlockId(selectedBlockId === block.block_id ? null : block.block_id)}
                  />
                ))}
              </div>
            ) : activeTab === "markdown" ? (
              <CodeBlock code={markdown || "# No markdown assembled yet"} language="Markdown" maxHeight={600} />
            ) : (
              <CodeBlock code={JSON.stringify(parseBlocks, null, 2)} language="JSON" maxHeight={600} />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Header({ complete, running }: { complete: boolean; running: boolean }) {
  return (
    <div className="flex min-h-12 items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
      <div>
        <h1 className="text-2xl font-medium">Parse</h1>
        <p className="text-sm text-[var(--text-secondary)]">Turn documents into structured blocks</p>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] text-[var(--text-muted)]">ws {getWorkspaceId().slice(0, 8)}</span>
        <Badge label={running ? "running" : complete ? "complete" : "idle"} status={running ? "info" : complete ? "success" : "neutral"} />
        <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
          <input defaultChecked className="accent-[var(--brand)]" type="checkbox" />
          confidence calibration
        </label>
      </div>
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

function ConfigToggle({ checked, label, onChange, tip }: { checked: boolean; label: string; onChange: (checked: boolean) => void; tip: string }) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
      <span>
        <span className="block font-mono text-xs text-[var(--text-primary)]">{label}</span>
        <span className="block text-xs text-[var(--text-muted)]">{tip}</span>
      </span>
      <input checked={checked} className="accent-[var(--brand)]" onChange={(event) => onChange(event.target.checked)} type="checkbox" />
    </label>
  );
}

function EmptyState({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="grid min-h-[360px] place-items-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-2)] text-center">
      <div>
        <i className={`ti ${icon} text-3xl text-[var(--text-muted)]`} />
        <p className="mt-3 text-sm text-[var(--text-secondary)]">{text}</p>
      </div>
    </div>
  );
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : "Operation failed";
}
