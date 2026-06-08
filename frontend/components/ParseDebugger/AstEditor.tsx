"use client";

import dynamic from "next/dynamic";

import { ConfidencePill } from "@/components/ui/confidence-pill";
import type { ParseBlock } from "@/lib/types";
import { useParseStore } from "@/lib/store";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="p-3 text-sm font-semibold text-muted">Loading JSON editor</div>
});

interface AstEditorProps {
  blocks: ParseBlock[];
}

export function AstEditor({ blocks }: AstEditorProps) {
  const selectedBlockId = useParseStore((state) => state.selectedBlockId);
  const setSelectedBlockId = useParseStore((state) => state.setSelectedBlockId);
  const selectedBlock = blocks.find((block) => block.block_id === selectedBlockId);
  const ast = JSON.stringify(selectedBlock ?? blocks, null, 2);

  return (
    <section className="flex min-h-0 flex-1 flex-col bg-panel">
      <div className="flex min-h-11 items-center justify-between gap-2 border-b border-line px-3">
        <h2 className="text-sm font-black">JSON AST</h2>
        {selectedBlock ? (
          <ConfidencePill
            calibrated={selectedBlock.confidence.calibrated}
            raw={selectedBlock.confidence.raw}
          />
        ) : null}
      </div>
      <div className="soft-scrollbar flex overflow-x-auto border-b border-line bg-[#f8fbfc]">
        {blocks.map((block) => (
          <button
            key={block.block_id}
            className={`min-w-[132px] border-r border-line px-3 py-2 text-left text-xs transition ${
              block.block_id === selectedBlockId
                ? "bg-[#e8faf7] text-teal"
                : "bg-white text-ink hover:bg-[#edf5ff]"
            }`}
            onClick={() => setSelectedBlockId(block.block_id)}
            type="button"
          >
            <span className="block truncate font-black">{block.type}</span>
            <span className="block truncate text-muted">{block.block_id}</span>
          </button>
        ))}
      </div>
      <div className="monaco-shell flex-1">
        <MonacoEditor
          height="100%"
          language="json"
          options={{
            minimap: { enabled: false },
            readOnly: true,
            fontSize: 13,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            renderLineHighlight: "none"
          }}
          theme="vs"
          value={ast}
        />
      </div>
    </section>
  );
}
