"use client";

import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { triggerClassification } from "@/lib/api";
import { getWorkspaceId } from "@/lib/config";
import { useParseStore } from "@/lib/store";
import type { ClassificationCategory, ClassificationResult } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/Card";
import { PageTimeline } from "@/components/ops/PageTimeline";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";

const swatches = ["#0EA5E9", "#22C55E", "#F59E0B", "#EF4444", "#A78BFA", "#14B8A6"];

export function ClassifyPanel() {
  const toast = useToast();
  const parseRunIdFromStore = useParseStore((state) => state.parseRunId);
  const [parseRunId, setParseRunId] = useState(parseRunIdFromStore ?? "");
  const [categories, setCategories] = useState<ClassificationCategory[]>([
    { label: "invoice", description: "Bills, purchase orders, and payment requests", color: swatches[0] },
    { label: "contract", description: "Legal agreements, amendments, and terms", color: swatches[4] },
    { label: "appendix", description: "Supporting schedules, exhibits, or addenda", color: swatches[2] }
  ]);
  const [results, setResults] = useState<ClassificationResult[]>([]);
  const [classifyStatus, setClassifyStatus] = useState<"idle" | "running" | "complete" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);
  const colorByLabel = useMemo<Record<string, string>>(
    () => ({ ...Object.fromEntries(categories.map((category) => [category.label, category.color])), uncertain: "#55555F" }),
    [categories],
  );
  const loading = classifyStatus === "running";

  async function classify() {
    if (!parseRunId.trim()) {
      setError("Paste a Parse Run ID to classify document pages");
      return;
    }
    setClassifyStatus("running");
    setError(null);
    try {
      const response = await triggerClassification(parseRunId.trim(), categories);
      setResults(response.classifications ?? response.results ?? []);
      setClassifyStatus("complete");
      toast.success("Classification complete");
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Classification failed";
      setClassifyStatus("failed");
      setError(message);
      toast.error(message);
    }
  }

  const sortedResults = [...results].sort((left, right) => left.page_num - right.page_num);

  return (
    <div className="min-h-screen p-6">
      <Header />
      <div className="mt-5 grid gap-5">
        <Card className="grid gap-4 p-5 md:grid-cols-[1fr_1fr]">
          <div>
            <p className="font-mono text-[11px] uppercase text-[var(--text-muted)]">Input</p>
            <div className="mt-3 flex gap-2">
              <input
                id="primary-input"
                className="h-9 min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-3 font-mono text-sm"
                onChange={(event) => setParseRunId(event.target.value)}
                placeholder="Parse Run ID"
                value={parseRunId}
              />
              <Button onClick={() => setError(null)}>Load</Button>
            </div>
          </div>
          <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
            <p className="font-mono text-xs text-[var(--text-muted)]">Loaded document preview</p>
            <div className="mt-2 flex items-center justify-between">
              <span className="truncate text-sm">{parseRunId ? `run:${parseRunId.slice(0, 12)}` : "No parse run loaded"}</span>
              <Badge label={parseRunId ? "ready" : "idle"} status={parseRunId ? "success" : "neutral"} />
            </div>
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-[11px] uppercase text-[var(--text-muted)]">Taxonomy builder</p>
              <h2 className="mt-1 text-base font-medium">Define your categories</h2>
            </div>
            <Button icon={<Plus size={15} />} onClick={() => setCategories((current) => [...current, { label: "", description: "", color: swatches[current.length % swatches.length] }])}>
              Add Category
            </Button>
          </div>
          <div className="mt-4 grid gap-2">
            {categories.map((category, index) => (
              <div className="grid gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3 lg:grid-cols-[180px_1fr_170px_36px]" key={`${category.label}-${index}`}>
                <input
                  className="h-9 rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-2 font-mono text-sm"
                  onChange={(event) => updateCategory(index, { ...category, label: event.target.value })}
                  placeholder="label"
                  value={category.label}
                />
                <input
                  className="h-9 rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-2 text-sm"
                  onChange={(event) => updateCategory(index, { ...category, description: event.target.value })}
                  placeholder="Natural-language rule"
                  value={category.description}
                />
                <div className="flex items-center gap-2">
                  {swatches.map((color) => (
                    <button
                      aria-label={`Use ${color}`}
                      className={`h-6 w-6 rounded border ${category.color === color ? "border-white" : "border-transparent"}`}
                      key={color}
                      onClick={() => updateCategory(index, { ...category, color })}
                      style={{ backgroundColor: color }}
                      type="button"
                    />
                  ))}
                </div>
                <Button aria-label="Delete category" className="h-9 w-9 px-0" icon={<Trash2 size={14} />} onClick={() => setCategories((current) => current.filter((_, itemIndex) => itemIndex !== index))} variant="ghost" />
              </div>
            ))}
          </div>
          <Button className="mt-4" disabled={loading} onClick={classify} variant="primary">
            {loading ? <Spinner /> : null}
            Classify Document
          </Button>
          {error ? <ErrorBox message={error} /> : null}
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">Results</h2>
            <Badge label={classifyStatus === "idle" ? `${results.length} pages` : classifyStatus} status={classifyStatus === "complete" ? "success" : classifyStatus === "failed" ? "error" : results.length ? "info" : "neutral"} />
          </div>
          {loading ? (
            <div className="mt-5 grid gap-3">
              <Skeleton height={96} width="100%" borderRadius={8} />
              <Skeleton height={160} width="100%" borderRadius={8} />
            </div>
          ) : sortedResults.length ? (
            <>
              <div className="mt-5">
                <PageTimeline classifications={sortedResults} colors={colorByLabel} />
              </div>
              <div className="mt-5 overflow-hidden rounded-lg border border-[var(--border)]">
                <table className="w-full border-collapse text-sm">
                  <thead className="bg-[var(--surface-2)] text-left text-xs uppercase text-[var(--text-muted)]">
                    <tr>
                      <th className="p-3">Page</th>
                      <th className="p-3">Category</th>
                      <th className="p-3">Confidence</th>
                      <th className="p-3">Top Alternative</th>
                      <th className="p-3">Scores</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedResults.map((result) => {
                      const alternatives = Object.entries(result.scores ?? {}).sort((a, b) => b[1] - a[1]);
                      const topAlternative = alternatives.find(([label]) => label !== result.label);
                      return (
                        <tr className="border-t border-[var(--border)]" key={result.page_num} style={{ backgroundColor: `${colorByLabel[result.label] ?? "#55555F"}14` }}>
                          <td className="p-3 font-mono">{result.page_num + 1}</td>
                          <td className="p-3">{result.label}</td>
                          <td className="p-3">
                            <div className="h-1.5 rounded bg-[var(--surface-3)]">
                              <div className="h-full rounded bg-[var(--brand)]" style={{ width: `${result.confidence * 100}%` }} />
                            </div>
                            <span className="font-mono text-xs text-[var(--text-muted)]">{result.confidence.toFixed(2)}</span>
                          </td>
                          <td className="p-3">{topAlternative ? `${topAlternative[0]} (${topAlternative[1].toFixed(2)})` : "--"}</td>
                          <td className="p-3 font-mono text-xs text-[var(--text-muted)]">{alternatives.map(([label, score]) => `${label}:${score.toFixed(2)}`).join(" ")}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <EmptyState />
          )}
        </Card>
      </div>
    </div>
  );

  function updateCategory(index: number, category: ClassificationCategory) {
    setCategories((current) => current.map((item, itemIndex) => (itemIndex === index ? category : item)));
  }
}

function Header() {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] pb-4">
      <div>
        <h1 className="text-2xl font-medium">Classify</h1>
        <p className="text-sm text-[var(--text-secondary)]">Route document pages into natural-language categories</p>
      </div>
      <span className="font-mono text-[11px] text-[var(--text-muted)]">ws {getWorkspaceId().slice(0, 8)}</span>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mt-5 grid min-h-[260px] place-items-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-2)] text-center">
      <div>
        <i className="ti ti-tag text-3xl text-[var(--text-muted)]" />
        <p className="mt-3 text-sm text-[var(--text-secondary)]">Paste a Parse Run ID to classify document pages</p>
      </div>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <div className="mt-4 rounded-md border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] p-3 text-sm text-[var(--red)]">{message}</div>;
}
