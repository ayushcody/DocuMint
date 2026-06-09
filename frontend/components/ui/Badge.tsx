import clsx from "clsx";

type BadgeStatus = "success" | "warning" | "error" | "info" | "neutral" | "ai";

const styles: Record<BadgeStatus, string> = {
  success: "bg-[rgba(34,197,94,0.12)] text-[var(--green)]",
  warning: "bg-[rgba(245,158,11,0.12)] text-[var(--amber)]",
  error: "bg-[rgba(239,68,68,0.12)] text-[var(--red)]",
  info: "bg-[rgba(14,165,233,0.12)] text-[var(--brand)]",
  neutral: "bg-[var(--surface-3)] text-[var(--text-secondary)]",
  ai: "bg-[rgba(167,139,250,0.12)] text-[var(--purple)]"
};

export function Badge({ className, label, status }: { className?: string; label: string; status: BadgeStatus }) {
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium", styles[status], className)}>
      {label}
    </span>
  );
}
