"use client";

import { FileWarning } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";

import { getHeatmapFill } from "@/components/ConfidenceHeatmap";
import { useParseStore } from "@/lib/store";
import type { ParseBlock, ParseBlockType } from "@/lib/types";

GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

interface PDFViewerProps {
  fileUrl: string | null;
  blocks: ParseBlock[];
}

export function PDFViewer({ fileUrl, blocks }: PDFViewerProps) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPdf(null);
    setLoadError(null);

    if (!fileUrl) {
      return () => {
        cancelled = true;
      };
    }

    const loadingTask = getDocument(fileUrl);
    void loadingTask.promise
      .then((document) => {
        if (!cancelled) {
          setPdf(document);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Unable to load PDF");
        }
      });

    return () => {
      cancelled = true;
      loadingTask.destroy();
    };
  }, [fileUrl]);

  const pageNumbers = useMemo(
    () => (pdf ? Array.from({ length: pdf.numPages }, (_, index) => index + 1) : []),
    [pdf],
  );

  if (!fileUrl) {
    return (
      <div className="soft-scrollbar flex flex-1 items-center justify-center overflow-auto bg-[linear-gradient(135deg,#e8faf7_0%,#f9fbff_48%,#fff7e8_100%)] p-4">
        <div className="max-w-sm rounded-lg border border-dashed border-line bg-white/90 p-5 text-center shadow-sm">
          <FileWarning aria-hidden className="mx-auto mb-3 text-sky" size={28} />
          <div className="text-sm font-black">Upload a PDF to inspect live parse output</div>
          <p className="mt-1 text-sm font-semibold text-muted">
            The canvas will render real PDF pages and draw returned bbox citations here.
          </p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="soft-scrollbar flex flex-1 items-center justify-center overflow-auto bg-[#fff8f8] p-4">
        <div className="rounded-lg border border-coral/40 bg-white p-4 text-sm font-semibold text-coral">
          {loadError}
        </div>
      </div>
    );
  }

  return (
    <div className="soft-scrollbar flex-1 overflow-auto bg-[linear-gradient(135deg,#e8faf7_0%,#f9fbff_48%,#fff7e8_100%)] p-4">
      <div className="mx-auto grid w-fit gap-4">
        {pdf ? (
          pageNumbers.map((pageNumber) => (
            <PDFPageCanvas
              key={pageNumber}
              blocks={blocks.filter((block) => block.page === pageNumber - 1)}
              pageNumber={pageNumber}
              pdf={pdf}
            />
          ))
        ) : (
          <div className="rounded-lg border border-line bg-white px-4 py-3 text-sm font-semibold text-muted">
            Loading PDF...
          </div>
        )}
      </div>
    </div>
  );
}

interface PDFPageCanvasProps {
  pdf: PDFDocumentProxy;
  pageNumber: number;
  blocks: ParseBlock[];
}

function PDFPageCanvas({ pdf, pageNumber, blocks }: PDFPageCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [page, setPage] = useState<PDFPageProxy | null>(null);
  const selectedBlockId = useParseStore((state) => state.selectedBlockId);
  const hoveredBlockId = useParseStore((state) => state.hoveredBlockId);
  const zoomLevel = useParseStore((state) => state.zoomLevel);
  const heatmapEnabled = useParseStore((state) => state.heatmapEnabled);
  const setSelectedBlockId = useParseStore((state) => state.setSelectedBlockId);
  const setHoveredBlockId = useParseStore((state) => state.setHoveredBlockId);

  useEffect(() => {
    let cancelled = false;
    void pdf.getPage(pageNumber).then((loadedPage) => {
      if (!cancelled) {
        setPage(loadedPage);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [pageNumber, pdf]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !page) {
      return;
    }

    let cancelled = false;
    const viewport = page.getViewport({ scale: zoomLevel });
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * dpr);
    canvas.height = Math.floor(viewport.height * dpr);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, viewport.width, viewport.height);

    const renderTask = page.render({
      canvasContext: ctx,
      viewport
    });

    void renderTask.promise
      .then(() => {
        if (cancelled) {
          return;
        }
        drawBlocks(ctx, blocks, viewport.width, viewport.height, {
          heatmapEnabled,
          hoveredBlockId,
          selectedBlockId
        });
      })
      .catch(() => {
        if (!cancelled) {
          setPage(null);
        }
      });

    return () => {
      cancelled = true;
      renderTask.cancel();
    };
  }, [blocks, heatmapEnabled, hoveredBlockId, page, selectedBlockId, zoomLevel]);

  function handleClick(event: ReactMouseEvent<HTMLCanvasElement>) {
    setSelectedBlockId(hitTest(event, blocks));
  }

  function handleMouseMove(event: ReactMouseEvent<HTMLCanvasElement>) {
    const hitBlockId = hitTest(event, blocks);
    event.currentTarget.style.cursor = hitBlockId ? "pointer" : "default";
    const block = blocks.find((item) => item.block_id === hitBlockId);
    event.currentTarget.title = block
      ? `${block.block_id} calibrated=${block.confidence.calibrated.toFixed(2)} raw=${block.confidence.raw.toFixed(2)}`
      : "";
    setHoveredBlockId(hitBlockId);
  }

  return (
    <div className="rounded-lg border border-line bg-white p-2 shadow-dock">
      <div className="mb-2 flex items-center justify-between px-1 text-xs font-bold text-muted">
        <span>Page {pageNumber}</span>
        <span>{blocks.length} blocks</span>
      </div>
      <canvas
        ref={canvasRef}
        className="block rounded-md bg-white shadow-sm"
        onClick={handleClick}
        onMouseLeave={() => setHoveredBlockId(null)}
        onMouseMove={handleMouseMove}
      />
    </div>
  );
}

interface DrawState {
  heatmapEnabled: boolean;
  hoveredBlockId: string | null;
  selectedBlockId: string | null;
}

function drawBlocks(
  ctx: CanvasRenderingContext2D,
  blocks: ParseBlock[],
  width: number,
  height: number,
  state: DrawState,
) {
  for (const block of blocks) {
    const rect = toCanvasRect(block, width, height);
    const isSelected = block.block_id === state.selectedBlockId;
    const isHovered = block.block_id === state.hoveredBlockId;

    if (state.heatmapEnabled) {
      const fill = getHeatmapFill(block.confidence.calibrated);
      if (fill) {
        ctx.fillStyle = fill;
        ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
      }
    }

    ctx.lineWidth = isSelected ? 4 : isHovered ? 3 : 1.5;
    ctx.strokeStyle = isSelected
      ? "rgba(59, 130, 246, 0.92)"
      : isHovered
        ? "#f4a127"
        : getColorForBlockType(block.type);
    ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
  }
}

function hitTest(event: ReactMouseEvent<HTMLCanvasElement>, blocks: ParseBlock[]): string | null {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  const hit = [...blocks].reverse().find((block) => {
    const blockRect = toCanvasRect(block, rect.width, rect.height);
    return (
      x >= blockRect.x &&
      x <= blockRect.x + blockRect.w &&
      y >= blockRect.y &&
      y <= blockRect.y + blockRect.h
    );
  });

  return hit?.block_id ?? null;
}

function toCanvasRect(block: ParseBlock, width: number, height: number) {
  return {
    x: block.bbox.x * width,
    y: block.bbox.y * height,
    w: block.bbox.w * width,
    h: block.bbox.h * height
  };
}

function getColorForBlockType(type: ParseBlockType): string {
  const colorByType: Record<ParseBlockType, string> = {
    table: "#2f80ed",
    paragraph: "#61706b",
    header: "#0f766e",
    figure: "#9d5b03",
    equation: "#7c3aed",
    form: "#e15b64",
    handwriting: "#d946ef",
    footer: "#475569"
  };
  return colorByType[type];
}
