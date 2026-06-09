"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/", icon: "ti-home", label: "Home" },
  { href: "/parse", icon: "ti-file-text", label: "Parse" },
  { href: "/extract", icon: "ti-json", label: "Extract" },
  { href: "/classify", icon: "ti-tag", label: "Classify" },
  { href: "/split", icon: "ti-scissors", label: "Split" },
  { href: "/index", icon: "ti-search", label: "Index" },
  { type: "divider" as const },
  { href: "/docs", icon: "ti-book", label: "Docs" }
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-20 flex h-screen w-[240px] flex-col border-r border-[var(--border)] bg-[var(--surface-1)] max-[1023px]:w-[72px] max-[767px]:bottom-0 max-[767px]:top-auto max-[767px]:h-[64px] max-[767px]:w-full max-[767px]:flex-row max-[767px]:border-r-0 max-[767px]:border-t">
      <div className="flex h-16 items-center gap-2 border-b border-[var(--border)] px-5 max-[1023px]:justify-center max-[1023px]:px-0 max-[767px]:hidden">
        <span className="font-mono text-[15px] font-medium text-[var(--brand)]">DocuMind</span>
        <span className="rounded bg-[rgba(167,139,250,0.12)] px-1.5 py-0.5 font-mono text-[10px] font-medium text-[var(--purple)]">
          AI
        </span>
      </div>
      <nav className="flex-1 p-3 max-[767px]:flex max-[767px]:items-center max-[767px]:justify-around max-[767px]:p-2">
        {nav.map((item, index) => {
          if ("type" in item) {
            return <div className="my-3 h-px bg-[var(--border)] max-[767px]:hidden" key={`divider-${index}`} />;
          }
          const active = pathname === item.href;
          return (
            <Link
              className={`mb-1 flex h-10 items-center gap-2 rounded-md border-l-2 px-3 text-[13px] transition max-[1023px]:justify-center max-[1023px]:px-0 max-[767px]:mb-0 max-[767px]:h-11 max-[767px]:w-11 ${
                active
                  ? "border-[var(--brand)] bg-[var(--surface-3)] text-[var(--text-primary)]"
                  : "border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
              }`}
              href={item.href}
              key={item.href}
              title={item.label}
            >
              <i className={`ti ${item.icon} text-base`} />
              <span className="max-[1023px]:hidden">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-[var(--border)] p-4 font-mono text-xs text-[var(--text-muted)] max-[1023px]:hidden max-[767px]:hidden">
        v0.1.0
      </div>
    </aside>
  );
}
