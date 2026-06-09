"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";

export function FileDropzone({
  accept = "application/pdf",
  label = "Drop PDF or image here",
  onFile
}: {
  accept?: string;
  label?: string;
  onFile: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  function selectFile(nextFile: File | undefined) {
    if (!nextFile) {
      return;
    }
    if (nextFile.size > 50 * 1024 * 1024) {
      setError("Max file size is 50MB");
      return;
    }
    setError(null);
    setFile(nextFile);
    onFile(nextFile);
  }

  return (
    <button
      className={`grid h-[140px] w-full place-items-center rounded-lg border border-dashed bg-[var(--surface-2)] p-4 text-center transition ${
        dragging ? "border-[var(--brand)] bg-[rgba(14,165,233,0.08)]" : "border-[var(--border)] hover:border-[var(--border-bright)]"
      }`}
      onClick={() => inputRef.current?.click()}
      onDragLeave={() => setDragging(false)}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        selectFile(event.dataTransfer.files[0]);
      }}
      type="button"
    >
      <input
        accept={accept}
        className="hidden"
        onChange={(event) => selectFile(event.target.files?.[0])}
        ref={inputRef}
        type="file"
      />
      <span>
        <Upload className="mx-auto mb-3 text-[var(--text-muted)]" size={32} />
        <span className="block text-sm text-[var(--text-primary)]">{file ? file.name : label}</span>
        <span className="mt-1 block font-mono text-xs text-[var(--text-muted)]">
          {error ?? (file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "or click to browse")}
        </span>
      </span>
    </button>
  );
}
