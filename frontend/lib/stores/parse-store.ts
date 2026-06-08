"use client";

import { create } from "zustand";

import type { ExtractionResult, ParseBlock, ParseRunStatus } from "@/lib/types";

interface ParseStoreState {
  selectedBlockId: string | null;
  hoveredBlockId: string | null;
  zoomLevel: number;
  heatmapEnabled: boolean;
  parseBlocks: ParseBlock[];
  extractionResult: ExtractionResult | null;
  pdfFile: File | null;
  pdfUrl: string | null;
  parseRunId: string | null;
  parseStatus: ParseRunStatus | null;
  errorMessage: string | null;
  setSelectedBlockId: (blockId: string | null) => void;
  setHoveredBlockId: (blockId: string | null) => void;
  setZoomLevel: (zoomLevel: number) => void;
  setHeatmapEnabled: (enabled: boolean) => void;
  setParseBlocks: (blocks: ParseBlock[]) => void;
  setExtractionResult: (result: ExtractionResult | null) => void;
  setPdfFile: (file: File | null, url: string | null) => void;
  setParseRunId: (id: string | null) => void;
  setParseStatus: (status: ParseRunStatus | null) => void;
  setErrorMessage: (message: string | null) => void;
}

export const useParseStore = create<ParseStoreState>((set) => ({
  selectedBlockId: null,
  hoveredBlockId: null,
  zoomLevel: 1,
  heatmapEnabled: true,
  parseBlocks: [],
  extractionResult: null,
  pdfFile: null,
  pdfUrl: null,
  parseRunId: null,
  parseStatus: null,
  errorMessage: null,
  setSelectedBlockId: (selectedBlockId) => set({ selectedBlockId }),
  setHoveredBlockId: (hoveredBlockId) => set({ hoveredBlockId }),
  setZoomLevel: (zoomLevel) => set({ zoomLevel }),
  setHeatmapEnabled: (heatmapEnabled) => set({ heatmapEnabled }),
  setParseBlocks: (blocks) =>
    set((state) => ({
      parseBlocks: blocks,
      selectedBlockId:
        state.selectedBlockId && blocks.some((block) => block.block_id === state.selectedBlockId)
          ? state.selectedBlockId
          : blocks[0]?.block_id ?? null
    })),
  setExtractionResult: (extractionResult) => set({ extractionResult }),
  setPdfFile: (pdfFile, pdfUrl) => set({ pdfFile, pdfUrl }),
  setParseRunId: (parseRunId) => set({ parseRunId }),
  setParseStatus: (parseStatus) => set({ parseStatus }),
  setErrorMessage: (errorMessage) => set({ errorMessage })
}));
