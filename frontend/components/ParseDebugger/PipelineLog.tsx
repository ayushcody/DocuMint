interface PipelineLogProps {
  timings: Record<string, number>;
}

export function PipelineLog({ timings }: PipelineLogProps) {
  const entries = Object.entries(timings);

  return (
    <div className="grid grid-cols-3 gap-2 border-t border-line bg-white/80 p-3 text-xs md:grid-cols-6">
      {entries.map(([agent, ms], index) => (
        <div
          key={agent}
          className="rounded-lg border border-line bg-white px-2 py-2 shadow-sm transition hover:-translate-y-0.5"
        >
          <div className="flex items-center gap-1.5 font-black capitalize">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: index % 3 === 0 ? "#0f766e" : index % 3 === 1 ? "#2f80ed" : "#f4a127" }}
            />
            {agent}
          </div>
          <div className="mt-0.5 text-muted">{ms} ms</div>
        </div>
      ))}
    </div>
  );
}
