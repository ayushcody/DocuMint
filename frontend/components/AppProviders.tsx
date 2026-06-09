"use client";

import { useEffect } from "react";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastProvider } from "@/components/ui/Toast";

export function AppProviders({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.getElementById("primary-input")?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <ToastProvider>
      <ErrorBoundary>{children}</ErrorBoundary>
    </ToastProvider>
  );
}
