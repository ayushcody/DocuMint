import type { ButtonHTMLAttributes, ReactNode } from "react";

import clsx from "clsx";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger" | "sunny";
}

export function Button({
  children,
  className,
  icon,
  variant = "secondary",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        "inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition duration-150 focus:outline-none focus:ring-2 focus:ring-teal focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" &&
          "border-teal bg-teal text-white shadow-glow hover:-translate-y-0.5 hover:bg-[#0b665f] active:translate-y-0",
        variant === "secondary" &&
          "border-line bg-panel text-ink shadow-sm hover:-translate-y-0.5 hover:border-[#b7c8ce] hover:bg-[#f8fbfc] active:translate-y-0",
        variant === "ghost" && "border-transparent bg-transparent text-ink hover:bg-[#edf4f5]",
        variant === "danger" && "border-coral bg-coral text-white hover:bg-[#c94750]",
        variant === "sunny" &&
          "border-[#e79218] bg-amber text-[#311d03] shadow-sm hover:-translate-y-0.5 hover:bg-[#efa03a] active:translate-y-0",
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
