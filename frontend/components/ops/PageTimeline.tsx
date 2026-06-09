"use client";

import { useState } from "react";

import type { ClassificationResult } from "@/lib/types";

export function PageTimeline({
  classifications,
  colors
}: {
  classifications: ClassificationResult[];
  colors: Record<string, string>;
}) {
  const [hoveredPage, setHoveredPage] = useState<number | null>(null);

  return (
    <div>
      <div className="flex h-12 overflow-hidden rounded-md border border-[var(--border)] bg-[var(--surface-2)]">
        {classifications.map((classification) => {
          const color = colors[classification.label] ?? colors.uncertain ?? "#55555F";
          const isHovered = hoveredPage === classification.page_num;
          return (
            <div
              className="relative min-w-1 flex-1 cursor-pointer transition-opacity"
              key={classification.page_num}
              onMouseEnter={() => setHoveredPage(classification.page_num)}
              onMouseLeave={() => setHoveredPage(null)}
              style={{ background: color, opacity: isHovered ? 1 : 0.75 }}
              title={`Page ${classification.page_num + 1}: ${classification.label} (${(classification.confidence * 100).toFixed(0)}%)`}
            />
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-4">
        {Object.entries(colors).map(([label, color]) => (
          <div className="flex items-center gap-1.5" key={label}>
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color, opacity: 0.75 }} />
            <span className="text-xs text-[var(--text-secondary)]">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
