"use client";

import { Check, Copy } from "lucide-react";
import { useMemo, useState } from "react";

export function CodeBlock({
  code,
  language = "JSON",
  maxHeight
}: {
  code: string;
  language?: string;
  maxHeight?: number;
}) {
  const [copied, setCopied] = useState(false);
  const highlighted = useMemo(() => highlightJsonish(truncateLongStrings(code)), [code]);

  async function copyCode() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="relative rounded-lg border border-[var(--border)] bg-[var(--surface-3)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <span className="font-mono text-[11px] uppercase text-[var(--text-muted)]">{language}</span>
        <button
          aria-label="Copy code"
          className="grid h-7 w-7 place-items-center rounded text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
          onClick={copyCode}
          type="button"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
      <pre
        className="soft-scrollbar overflow-auto p-3 font-mono text-xs leading-6 text-[var(--text-secondary)]"
        style={maxHeight ? { maxHeight } : undefined}
      >
        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>
    </div>
  );
}

function truncateLongStrings(input: string) {
  return input.replace(/"([^"\\]*(?:\\.[^"\\]*)*)"/g, (match, value: string) => {
    if (value.length <= 500) {
      return match;
    }
    return `"${value.slice(0, 500)} [... ${value.length - 500} chars]"`;
  });
}

function highlightJsonish(input: string) {
  const escaped = input.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped
    .replace(/("[^"]+"\s*:)/g, '<span style="color: var(--brand)">$1</span>')
    .replace(/(:\s*)("[^"]*")/g, '$1<span style="color: var(--amber)">$2</span>')
    .replace(/\b(-?\d+(?:\.\d+)?)\b/g, '<span style="color: var(--green)">$1</span>');
}
