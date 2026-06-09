"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { X } from "lucide-react";

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const tone: Record<ToastType, string> = {
  success: "border-[rgba(34,197,94,0.3)] text-[var(--green)]",
  error: "border-[rgba(239,68,68,0.3)] text-[var(--red)]",
  info: "border-[rgba(14,165,233,0.3)] text-[var(--brand)]",
  warning: "border-[rgba(245,158,11,0.3)] text-[var(--amber)]"
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (type: ToastType, message: string) => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { id, type, message }]);
      window.setTimeout(() => remove(id), 4000);
    },
    [remove],
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push("success", message),
      error: (message) => push("error", message),
      info: (message) => push("info", message),
      warning: (message) => push("warning", message)
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed right-4 top-4 z-50 grid w-[min(360px,calc(100vw-32px))] gap-2">
        {toasts.map((toast) => (
          <div
            className={`toast-enter flex items-start justify-between gap-3 rounded-lg border bg-[var(--surface-2)] p-3 shadow-xl ${tone[toast.type]}`}
            key={toast.id}
          >
            <span className="text-sm text-[var(--text-primary)]">{toast.message}</span>
            <button
              aria-label="Dismiss toast"
              className="grid h-6 w-6 place-items-center rounded text-[var(--text-muted)] hover:bg-[var(--surface-3)] hover:text-[var(--text-primary)]"
              onClick={() => remove(toast.id)}
              type="button"
            >
              <X size={13} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used inside ToastProvider");
  }
  return context;
}
