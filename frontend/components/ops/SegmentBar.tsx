import type { SplitSegment } from "@/lib/types";

const SEGMENT_COLORS: Record<string, string> = {
  invoice: "#0EA5E9",
  contract: "#A78BFA",
  report: "#22C55E",
  appendix: "#F59E0B",
  statement: "#14B8A6",
  unknown: "#55555F"
};

export function SegmentBar({ segments, totalPages }: { segments: SplitSegment[]; totalPages: number }) {
  return (
    <div className="flex h-14 gap-0.5">
      {segments.map((segment, index) => {
        const pages = segment.end_page - segment.start_page + 1;
        const width = (pages / totalPages) * 100;
        const color = SEGMENT_COLORS[segment.label] ?? "#55555F";
        return (
          <div
            className="flex min-w-6 cursor-default flex-col justify-center overflow-hidden rounded px-2"
            key={`${segment.start_page}-${segment.end_page}-${index}`}
            style={{ background: color, opacity: 0.8, width: `${width}%` }}
            title={`Pages ${segment.start_page + 1}-${segment.end_page + 1}\n${segment.label}\nconf: ${segment.confidence?.toFixed(2)}\n${segment.evidence ?? ""}`}
          >
            {width > 10 ? (
              <>
                <span className="truncate text-[11px] font-medium text-white">{segment.label}</span>
                <span className="text-[10px] text-white/70">
                  pp. {segment.start_page + 1}-{segment.end_page + 1}
                </span>
              </>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
