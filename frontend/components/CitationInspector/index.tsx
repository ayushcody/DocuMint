"use client";

import { X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";

import { Button } from "@/components/ui/button";
import { getSignedUrl } from "@/lib/api";
import { useParseStore } from "@/lib/store";
import type { BBox, Citation, ParseBlock } from "@/lib/types";

GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

interface CitationInspectorProps {
  citation: Citation | null;
  pdfUrl: string | null;
  onClose: () => void;
}

export function CitationInspector({ citation, pdfUrl, onClose }: CitationInspectorProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const parseBlocks = useParseStore((state) => state.parseBlocks);
  const selectedBlockId = useParseStore((state) => state.selectedBlockId);
  const [dismissedBlockId, setDismissedBlockId] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const selectedBlock = useMemo(
    () => parseBlocks.find((block) => block.block_id === selectedBlockId) ?? null,
    [parseBlocks, selectedBlockId],
  );
  const effectiveCitation =
    citation ?? (selectedBlock?.block_id !== dismissedBlockId ? selectedBlock?.citations[0] : null) ?? null;
  const bbox = effectiveCitation?.bboxes[0] ?? null;
  const sourceBlock = useMemo(
    () => (effectiveCitation && bbox ? findSourceBlock(parseBlocks, effectiveCitation.page, bbox) : null),
    [bbox, effectiveCitation, parseBlocks],
  );

  useEffect(() => {
    if (selectedBlockId !== dismissedBlockId) {
      setDismissedBlockId(null);
    }
  }, [dismissedBlockId, selectedBlockId]);

  useEffect(() => {
    let cancelled = false;
    setRenderError(null);

    if (!effectiveCitation || !bbox) {
      return () => {
        cancelled = true;
      };
    }

    const currentCitation = effectiveCitation;
    const currentBbox = bbox;

    async function renderCitationCrop() {
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }
      const sourcePath = sourceBlock?.source.render_path ?? null;
      if (sourcePath) {
        const url = await getSignedUrl(sourcePath);
        await drawImageCrop(canvas, url, currentBbox);
        return;
      }
      if (pdfUrl) {
        await drawPdfCrop(canvas, pdfUrl, currentCitation.page + 1, currentBbox);
        return;
      }
      throw new Error("No render artifact or uploaded PDF is available for this citation");
    }

    void renderCitationCrop().catch((error: unknown) => {
      if (!cancelled) {
        setRenderError(error instanceof Error ? error.message : "Unable to render citation crop");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [bbox, effectiveCitation, pdfUrl, sourceBlock]);

  if (!effectiveCitation || !bbox) {
    return null;
  }

  function handleClose() {
    if (!citation) {
      setDismissedBlockId(selectedBlockId);
    }
    onClose();
  }

  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-[rgba(22,32,34,0.38)] p-4">
      <section className="w-full max-w-2xl rounded-lg border border-line bg-panel shadow-dock">
        <div className="flex items-center justify-between border-b border-line bg-[#f8fbfc] px-4 py-3">
          <h2 className="text-sm font-black">Citation</h2>
          <Button aria-label="Close citation" icon={<X size={16} />} onClick={handleClose} variant="ghost" />
        </div>
        <div className="grid gap-4 p-4 md:grid-cols-[1fr_260px]">
          <div>
            <div className="mb-2 text-xs font-bold uppercase text-muted">Matching text</div>
            <p className="rounded-md border border-line bg-[#f8fbfc] p-3 text-sm font-semibold">
              {effectiveCitation.matching_text || "No matching text returned"}
            </p>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt className="font-semibold text-muted">Page</dt>
                <dd className="font-black">{effectiveCitation.page + 1}</dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">Block</dt>
                <dd className="truncate font-black">{sourceBlock?.block_id ?? "not matched"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="font-semibold text-muted">BBox</dt>
                <dd className="font-black">
                  {bbox.x.toFixed(3)}, {bbox.y.toFixed(3)}, {bbox.w.toFixed(3)}, {bbox.h.toFixed(3)}
                </dd>
              </div>
            </dl>
          </div>
          <div className="min-h-48 rounded-md border border-line bg-white p-2">
            {renderError ? (
              <div className="grid h-48 place-items-center rounded-md bg-[#fff8f8] p-3 text-center text-sm font-semibold text-coral">
                {renderError}
              </div>
            ) : (
              <canvas ref={canvasRef} className="block h-auto w-full rounded-md bg-[#f8fbfc]" />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function findSourceBlock(blocks: ParseBlock[], page: number, bbox: BBox): ParseBlock | null {
  return (
    blocks
      .filter((block) => block.page === page)
      .sort((left, right) => bboxOverlap(right.bbox, bbox) - bboxOverlap(left.bbox, bbox))[0] ?? null
  );
}

function bboxOverlap(left: BBox, right: BBox): number {
  const x1 = Math.max(left.x, right.x);
  const y1 = Math.max(left.y, right.y);
  const x2 = Math.min(left.x + left.w, right.x + right.w);
  const y2 = Math.min(left.y + left.h, right.y + right.h);
  return Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
}

async function drawImageCrop(canvas: HTMLCanvasElement, imageUrl: string, bbox: BBox): Promise<void> {
  const image = await loadImage(imageUrl);
  const crop = toPixelCrop(bbox, image.naturalWidth, image.naturalHeight);
  drawCrop(canvas, image, crop);
}

async function drawPdfCrop(
  canvas: HTMLCanvasElement,
  pdfUrl: string,
  pageNumber: number,
  bbox: BBox,
): Promise<void> {
  const pdfDocument = await getDocument(pdfUrl).promise;
  const page = await pdfDocument.getPage(pageNumber);
  const viewport = page.getViewport({ scale: 2 });
  const scratch = document.createElement("canvas");
  scratch.width = Math.floor(viewport.width);
  scratch.height = Math.floor(viewport.height);
  const scratchContext = scratch.getContext("2d");
  if (!scratchContext) {
    throw new Error("Unable to create citation render context");
  }
  await page.render({ canvasContext: scratchContext, viewport }).promise;
  drawCrop(canvas, scratch, toPixelCrop(bbox, scratch.width, scratch.height));
  pdfDocument.destroy();
}

function drawCrop(
  canvas: HTMLCanvasElement,
  source: CanvasImageSource,
  crop: { sx: number; sy: number; sw: number; sh: number },
) {
  const displayWidth = 260;
  const displayHeight = Math.max(160, Math.round(displayWidth * (crop.sh / crop.sw)));
  const dpr = window.devicePixelRatio || 1;
  canvas.width = displayWidth * dpr;
  canvas.height = displayHeight * dpr;
  canvas.style.width = `${displayWidth}px`;
  canvas.style.height = `${displayHeight}px`;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Unable to draw citation crop");
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, displayWidth, displayHeight);
  ctx.drawImage(source, crop.sx, crop.sy, crop.sw, crop.sh, 0, 0, displayWidth, displayHeight);
  ctx.strokeStyle = "#0f766e";
  ctx.lineWidth = 3;
  ctx.strokeRect(1.5, 1.5, displayWidth - 3, displayHeight - 3);
}

function toPixelCrop(bbox: BBox, width: number, height: number) {
  return {
    sx: Math.max(0, Math.floor(bbox.x * width)),
    sy: Math.max(0, Math.floor(bbox.y * height)),
    sw: Math.max(1, Math.floor(bbox.w * width)),
    sh: Math.max(1, Math.floor(bbox.h * height))
  };
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Unable to load signed render artifact"));
    image.src = url;
  });
}
