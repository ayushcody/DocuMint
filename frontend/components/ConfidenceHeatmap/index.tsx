"use client";

import { Thermometer } from "lucide-react";

import { useParseStore } from "@/lib/store";

export function getHeatmapFill(score: number): string | null {
  if (score >= 0.85) {
    return null;
  }
  if (score >= 0.7) {
    return "rgba(251, 191, 36, 0.30)";
  }
  if (score >= 0.5) {
    return "rgba(239, 68, 68, 0.40)";
  }
  return "rgba(185, 28, 28, 0.60)";
}

export function ConfidenceHeatmap() {
  const enabled = useParseStore((state) => state.heatmapEnabled);
  const setEnabled = useParseStore((state) => state.setHeatmapEnabled);
  const selectedBlockId = useParseStore((state) => state.selectedBlockId);
  const parseBlocks = useParseStore((state) => state.parseBlocks);
  const selectedBlock = parseBlocks.find((block) => block.block_id === selectedBlockId);

  return (
    <div className="inline-flex min-h-9 items-center gap-2 rounded-md border border-line bg-panel px-3 text-sm font-semibold shadow-sm transition hover:border-[#b7c8ce] hover:bg-[#f8fbfc]">
      <label className="inline-flex cursor-pointer items-center gap-2">
        <Thermometer aria-hidden className="text-coral" size={16} />
        <input
          checked={enabled}
          className="h-4 w-4 accent-teal"
          onChange={(event) => setEnabled(event.target.checked)}
          type="checkbox"
        />
        Heatmap
      </label>
      {selectedBlock ? (
        <span className="hidden border-l border-line pl-2 text-xs font-black text-muted md:inline-flex">
          {selectedBlock.type} c={selectedBlock.confidence.calibrated.toFixed(2)} r=
          {selectedBlock.confidence.raw.toFixed(2)}
        </span>
      ) : null}
    </div>
  );
}

export function HeatmapLegend() {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-muted">
      <span className="inline-flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-sm bg-[#b91c1c] shadow-sm" />
        &lt; 0.50
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-sm bg-coral shadow-sm" />
        0.50-0.69
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-sm bg-amber shadow-sm" />
        0.70-0.84
      </span>
    </div>
  );
}
