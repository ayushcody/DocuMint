"use client";

import { PDFViewer } from "@/components/PDFViewer";
import { useParseStore } from "@/lib/store";
import type { ParseBlock } from "@/lib/types";

interface PDFCanvasProps {
  blocks: ParseBlock[];
}

export function PDFCanvas({ blocks }: PDFCanvasProps) {
  const pdfUrl = useParseStore((state) => state.pdfUrl);
  return <PDFViewer blocks={blocks} fileUrl={pdfUrl} />;
}
