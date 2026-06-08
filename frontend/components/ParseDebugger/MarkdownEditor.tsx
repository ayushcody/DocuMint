"use client";

import dynamic from "next/dynamic";

import type { ParseBlock } from "@/lib/types";
import { useParseStore } from "@/lib/store";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="p-3 text-sm font-semibold text-muted">Loading Markdown editor</div>
});

interface MarkdownEditorProps {
  blocks: ParseBlock[];
}

export function MarkdownEditor({ blocks }: MarkdownEditorProps) {
  const selectedBlockId = useParseStore((state) => state.selectedBlockId);
  const selectedBlock = blocks.find((block) => block.block_id === selectedBlockId);
  const markdown = selectedBlock?.text ?? blocks.map((block) => block.text).join("\n\n");

  return (
    <section className="flex min-h-0 flex-1 flex-col bg-panel">
      <div className="flex min-h-11 items-center justify-between gap-2 border-b border-line px-3">
        <h2 className="text-sm font-black">Markdown</h2>
        <span className="truncate rounded-md bg-[#fff7e8] px-2 py-1 text-xs font-bold text-[#9d5b03]">
          {selectedBlock?.block_id ?? "all blocks"}
        </span>
      </div>
      <div className="monaco-shell flex-1">
        <MonacoEditor
          height="100%"
          language="markdown"
          options={{
            minimap: { enabled: false },
            readOnly: true,
            fontSize: 13,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            renderLineHighlight: "none"
          }}
          theme="vs"
          value={markdown}
        />
      </div>
    </section>
  );
}
