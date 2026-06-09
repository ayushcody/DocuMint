import { Check } from "lucide-react";

type ProgressStatus = "running" | "complete" | "failed";

export function ProgressBar({
  currentStage,
  stages,
  status
}: {
  currentStage: number;
  stages: string[];
  status: ProgressStatus;
}) {
  return (
    <div className="w-full">
      <div className="grid" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
        {stages.map((stage, index) => {
          const complete = status === "complete" || index < currentStage;
          const current = status === "running" && index === currentStage;
          const failed = status === "failed" && index === currentStage;
          return (
            <div className="relative flex flex-col items-center gap-2" key={stage}>
              {index > 0 ? (
                <div className={`absolute right-1/2 top-[9px] h-px w-full ${complete ? "bg-[var(--brand)]" : "bg-[var(--border)]"}`} />
              ) : null}
              <div
                className={`relative z-10 grid h-5 w-5 place-items-center rounded-full border text-[10px] ${
                  complete
                    ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                    : failed
                      ? "border-[var(--red)] bg-[rgba(239,68,68,0.12)] text-[var(--red)]"
                      : current
                        ? "animate-pulse border-[var(--brand)] bg-[rgba(14,165,233,0.16)]"
                        : "border-[var(--border)] bg-[var(--surface-1)]"
                }`}
              >
                {complete ? <Check size={12} /> : null}
              </div>
              <span className="max-w-[92px] truncate text-center text-[11px] text-[var(--text-muted)]">{stage}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
