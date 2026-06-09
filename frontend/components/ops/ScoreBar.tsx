export function ScoreBar({ score }: { score: number }) {
  const normalized = Math.max(0, Math.min(1, Number.isFinite(score) ? score : 0));
  const color = normalized > 0.7 ? "var(--green)" : normalized > 0.4 ? "var(--brand)" : "var(--amber)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 flex-1 overflow-hidden rounded bg-[var(--surface-3)]">
        <div
          className="h-full rounded transition-[width] duration-700"
          style={{ background: color, width: `${normalized * 100}%` }}
        />
      </div>
      <span className="min-w-9 font-mono text-xs text-[var(--text-secondary)]">{normalized.toFixed(3)}</span>
    </div>
  );
}
