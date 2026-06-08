"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ParseBlock } from "@/lib/types";
import { useParseStore } from "@/lib/store";

interface ReviewQueueProps {
  blocks: ParseBlock[];
}

export function ReviewQueue({ blocks }: ReviewQueueProps) {
  const setSelectedBlockId = useParseStore((state) => state.setSelectedBlockId);
  const reviewBlocks = blocks.filter((block) => block.source.verifier.flag_for_repair);

  return (
    <section className="border-t border-line bg-panel p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-black">
        <AlertTriangle aria-hidden className="text-coral" size={16} />
        Review Queue
      </div>
      {reviewBlocks.length === 0 ? (
        <p className="rounded-md border border-line bg-[#f8fbfc] p-2 text-sm font-semibold text-muted">
          No flagged blocks
        </p>
      ) : (
        <div className="grid gap-2">
          {reviewBlocks.map((block) => (
            <div
              key={block.block_id}
              className="flex items-center justify-between gap-2 rounded-lg border border-coral/40 bg-[#fff8f8] p-2 shadow-sm"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-black">{block.block_id}</div>
                <div className="text-xs font-semibold text-muted">
                  L_verify {block.source.verifier.L_verify.toFixed(2)}
                </div>
              </div>
              <Button onClick={() => setSelectedBlockId(block.block_id)} variant="danger">
                Inspect
              </Button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
