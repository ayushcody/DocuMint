import type { ParseBlock } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";

const TYPE_COLORS: Record<string, string> = {
  text: "var(--text-secondary)",
  paragraph: "var(--text-secondary)",
  heading: "var(--brand)",
  header: "var(--brand)",
  table: "var(--purple)",
  figure: "var(--amber)",
  formula: "var(--green)",
  equation: "var(--green)",
  footer: "var(--text-muted)",
  form: "var(--purple)",
  handwriting: "var(--amber)"
};

export function BlockCard({
  block,
  isSelected,
  onClick
}: {
  block: ParseBlock;
  isSelected: boolean;
  onClick: () => void;
}) {
  const score = block.confidence.calibrated ?? block.confidence.overall ?? 0;
  const verifier = block.source.verifier;
  const typeColor = TYPE_COLORS[block.type] ?? "var(--text-secondary)";

  return (
    <button
      className={`w-full rounded-lg border bg-[var(--surface-2)] p-3 text-left transition ${
        isSelected ? "border-[var(--brand)]" : "border-[var(--border)] hover:border-[var(--border-bright)]"
      }`}
      onClick={onClick}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span
            className="inline-flex rounded-full px-2.5 py-1 text-xs font-medium"
            style={{ backgroundColor: `${typeColor}22`, color: typeColor }}
          >
            {block.type}
          </span>
          <span className="ml-2 font-mono text-[11px] text-[var(--text-muted)]">{block.block_id}</span>
          <p className="mt-2 line-clamp-2 text-sm text-[var(--text-secondary)]">{block.text || "No text returned"}</p>
        </div>
        <Badge label={`p${block.page + 1}`} status="neutral" />
      </div>
      <div className="mt-3">
        <ConfidenceBar label="conf" value={score} />
      </div>
      {isSelected ? (
        <div className="mt-4 grid gap-2 border-t border-[var(--border)] pt-3 font-mono text-[11px] text-[var(--text-secondary)]">
          <ConfidenceBar label="SSIM" value={verifier.components.ssim} />
          <ConfidenceBar label="IoU" value={verifier.components.layout_iou} />
          <ConfidenceBar label="CLIP" value={verifier.components.clip_sim} />
          <ConfidenceBar label="L_ver" value={Math.max(0, 1 - verifier.L_verify)} />
          <span>
            bbox: {block.bbox.x.toFixed(3)}, {block.bbox.y.toFixed(3)}, {block.bbox.w.toFixed(3)},{" "}
            {block.bbox.h.toFixed(3)}
          </span>
          <span>layout_backend: {block.source.layout_backend ?? "unknown"}</span>
          <span>citations: {block.citations.length}</span>
          <span className={verifier.L_verify > 0.15 ? "text-[var(--red)]" : "text-[var(--green)]"}>
            L_verify = {verifier.L_verify.toFixed(2)} - {verifier.L_verify > 0.15 ? "Flagged for Review" : "Verified"}
          </span>
        </div>
      ) : null}
    </button>
  );
}

function ConfidenceBar({ value, label }: { value: number; label: string }) {
  const normalized = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  const color = normalized >= 0.85 ? "var(--green)" : normalized >= 0.7 ? "var(--amber)" : "var(--red)";
  return (
    <div className="grid grid-cols-[48px_1fr_42px] items-center gap-2 text-[11px]">
      <span className="text-[var(--text-muted)]">{label}</span>
      <div className="h-[3px] overflow-hidden rounded bg-[var(--surface-3)]">
        <div
          className="h-full rounded transition-[width] duration-500"
          style={{ background: color, width: `${normalized * 100}%` }}
        />
      </div>
      <span className="text-right font-mono" style={{ color }}>
        {normalized.toFixed(2)}
      </span>
    </div>
  );
}
