import clsx from "clsx";

export function Skeleton({
  borderRadius = 4,
  className,
  height,
  width
}: {
  width: string | number;
  height: string | number;
  borderRadius?: number;
  className?: string;
}) {
  return (
    <div
      className={clsx("skeleton-shimmer relative overflow-hidden bg-[var(--surface-3)]", className)}
      style={{ width, height, borderRadius }}
    />
  );
}
