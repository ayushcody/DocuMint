import { Tooltip } from "@/components/ui/tooltip";

interface ConfidencePillProps {
  calibrated: number;
  raw: number;
}

export function ConfidencePill({ calibrated, raw }: ConfidencePillProps) {
  const tone =
    calibrated < 0.7
      ? "border-coral bg-[#fff0f1] text-[#b6323b]"
      : calibrated < 0.85
        ? "border-amber bg-[#fff7e8] text-[#9d5b03]"
        : "border-teal bg-[#e8faf7] text-teal";

  return (
    <Tooltip label="Calibrated confidence is post-hoc adjusted. Raw is the model score before calibration.">
      <span
        className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-bold shadow-sm ${tone}`}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-current" />
        cal {calibrated.toFixed(2)}
        <span className="text-current/60">raw {raw.toFixed(2)}</span>
      </span>
    </Tooltip>
  );
}
