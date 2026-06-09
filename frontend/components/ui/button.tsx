import type { ButtonHTMLAttributes, ReactNode } from "react";

import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "sunny";

export function Button({
  children,
  className,
  icon,
  variant = "secondary",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon?: ReactNode; variant?: Variant }) {
  return (
    <button
      className={clsx(
        "inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "border-[var(--brand)] bg-[var(--brand)] text-white hover:bg-[var(--brand-dim)]",
        variant === "secondary" &&
          "border-[var(--border)] bg-[var(--surface-2)] text-[var(--text-primary)] hover:border-[var(--border-bright)]",
        variant === "ghost" && "border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]",
        variant === "danger" && "border-[var(--red)] bg-[var(--red)] text-white hover:brightness-110",
        variant === "sunny" && "border-[var(--amber)] bg-[var(--amber)] text-[#311d03] hover:brightness-110",
        className
      )}
      type={type}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
