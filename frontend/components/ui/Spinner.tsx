import clsx from "clsx";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-label="Loading"
      className={clsx("inline-block h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-bright)] border-t-[var(--brand)]", className)}
    />
  );
}
