import type { HTMLAttributes } from "react";

import clsx from "clsx";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      className={clsx("rounded-lg border border-[var(--border)] bg-[var(--surface-1)]", className)}
      {...props}
    />
  );
}
