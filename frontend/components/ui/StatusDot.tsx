import clsx from "clsx";

type Status = "success" | "warning" | "error" | "info" | "neutral" | "running";

export function StatusDot({ status }: { status: Status }) {
  return (
    <span
      className={clsx(
        "inline-block h-2 w-2 rounded-full",
        status === "success" && "bg-[var(--green)]",
        status === "warning" && "bg-[var(--amber)]",
        status === "error" && "bg-[var(--red)]",
        status === "info" && "bg-[var(--brand)]",
        status === "neutral" && "bg-[var(--text-muted)]",
        status === "running" && "animate-pulse bg-[var(--brand)]"
      )}
    />
  );
}
