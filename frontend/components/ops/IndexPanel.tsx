"use client";

import { Plus, Search, X } from "lucide-react";
import { useEffect, useState } from "react";

import { createIndexCollection, getSignedUrl, listIndexCollections, queryIndex, syncIndexCollection } from "@/lib/api";
import { getWorkspaceId } from "@/lib/config";
import { useParseStore } from "@/lib/store";
import type { IndexCollection, RetrievalResult } from "@/lib/types";
import { ScoreBar } from "@/components/ops/ScoreBar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";

export function IndexPanel() {
  const toast = useToast();
  const parseRunIdFromStore = useParseStore((state) => state.parseRunId);
  const [collections, setCollections] = useState<IndexCollection[]>([]);
  const [activeCollectionId, setActiveCollectionId] = useState<string | null>(null);
  const [newCollectionName, setNewCollectionName] = useState("default");
  const [parseRunId, setParseRunId] = useState(parseRunIdFromStore ?? "");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<RetrievalResult[]>([]);
  const [loading, setLoading] = useState<"collection" | "sync" | "query" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [pageUrl, setPageUrl] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Array<{ id: string; pages: number; status: string }>>([]);
  const activeCollection = collections.find((collection) => collection.collection_id === activeCollectionId) ?? collections[0] ?? null;

  useEffect(() => {
    void loadCollections();
  }, []);

  async function loadCollections() {
    try {
      const nextCollections = await listIndexCollections();
      setCollections(nextCollections);
      setActiveCollectionId((current) => current ?? nextCollections[0]?.collection_id ?? null);
    } catch {
      setCollections([{ collection_id: "local-default", name: "default", page_count: 0, embedding_model: "vidore/colqwen2-v1.0" }]);
      setActiveCollectionId("local-default");
    }
  }

  async function newCollection() {
    const name = newCollectionName.trim();
    if (!name) {
      setError("Enter a collection name");
      return;
    }
    setLoading("collection");
    setError(null);
    try {
      const response = await createIndexCollection(name);
      const nextCollection = {
        collection_id: response.collection_id ?? response.id ?? name,
        name,
        page_count: 0,
        embedding_model: "vidore/colqwen2-v1.0"
      };
      setCollections((current) => [...current, nextCollection]);
      setActiveCollectionId(nextCollection.collection_id);
      toast.success("Collection created");
      void loadCollections();
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Collection creation failed";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(null);
    }
  }

  async function syncDocument() {
    if (!parseRunId.trim()) {
      setError("Paste a Parse Run ID before syncing");
      return;
    }
    setLoading("sync");
    setError(null);
    try {
      if (!activeCollection) {
        throw new Error("Create or select a collection before syncing");
      }
      const response = await syncIndexCollection(activeCollection.collection_id, parseRunId.trim());
      const pages = response.pages_to_index ?? 0;
      setSyncStatus(response.status);
      setDocuments((current) => [...current, { id: parseRunId.trim(), pages, status: response.status }]);
      setCollections((current) =>
        current.map((collection) =>
          collection.collection_id === activeCollection.collection_id
            ? { ...collection, page_count: collection.page_count + pages }
            : collection
        )
      );
      toast.success(`Sync ${response.status}`);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Index sync failed";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(null);
    }
  }

  async function runQuery() {
    if (!query.trim()) {
      return;
    }
    setLoading("query");
    setError(null);
    try {
      if (!activeCollection) {
        throw new Error("Create or select a collection before querying");
      }
      setHits(await queryIndex(activeCollection.collection_id, query.trim()));
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Search failed";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(null);
    }
  }

  async function viewPage(hit: RetrievalResult) {
    if (!hit.image_patch_path) {
      setError("No render artifact returned for this hit");
      return;
    }
    try {
      setPageUrl(await getSignedUrl(hit.image_patch_path));
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unable to open page render";
      setError(message);
      toast.error(message);
    }
  }

  return (
    <div className="min-h-screen p-6">
      <Header />
      <div className="mt-5 grid gap-5 xl:grid-cols-[220px_minmax(360px,0.42fr)_minmax(420px,1fr)]">
        <Card className="flex min-h-[650px] flex-col p-4">
          <h2 className="text-sm font-medium">Collections</h2>
          <div className="mt-4 flex gap-2">
            <input
              className="h-9 min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-2 text-sm"
              onChange={(event) => setNewCollectionName(event.target.value)}
              placeholder="collection name"
              value={newCollectionName}
            />
            <Button className="h-9 w-9 px-0" disabled={loading === "collection"} icon={loading === "collection" ? <Spinner /> : <Plus size={14} />} onClick={newCollection} />
          </div>
          <div className="mt-4 grid gap-2">
            {collections.length ? collections.map((collection) => (
              <button
                className={`rounded-md border p-3 text-left ${
                  collection.collection_id === activeCollection?.collection_id
                    ? "border-[var(--brand)] bg-[rgba(14,165,233,0.08)]"
                    : "border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--border-bright)]"
                }`}
                key={collection.collection_id}
                onClick={() => setActiveCollectionId(collection.collection_id)}
                type="button"
              >
                <span className="block text-sm text-[var(--text-primary)]">{collection.name}</span>
                <span className="mt-1 block font-mono text-[11px] text-[var(--text-muted)]">{collection.page_count} pages</span>
                <Badge className="mt-2" label={collection.embedding_model.replace("vidore/", "")} status="ai" />
              </button>
            )) : <Skeleton height={86} width="100%" borderRadius={8} />}
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-[11px] uppercase text-[var(--text-muted)]">Document sync</p>
              <h2 className="mt-1 text-base font-medium">{activeCollection?.name ?? "No collection"}</h2>
            </div>
            <Badge label="vidore/colqwen2-v1.0" status="ai" />
          </div>
          <div className="mt-5 grid gap-2">
            {documents.length ? (
              documents.map((document) => (
                <div className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3" key={document.id}>
                  <span className="truncate font-mono text-xs">{document.id}</span>
                  <span className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                    {document.pages} pages <Badge label={document.status} status="neutral" />
                  </span>
                </div>
              ))
            ) : (
              <div className="rounded-md border border-dashed border-[var(--border)] bg-[var(--surface-2)] p-8 text-center text-sm text-[var(--text-secondary)]">
                Create a collection and sync parsed documents to start querying
              </div>
            )}
          </div>
          <div className="mt-6 rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
            <label>
              <span className="text-xs text-[var(--text-muted)]">Sync Parse Run</span>
              <input
                id="primary-input"
                className="mt-1 h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-3 font-mono text-sm"
                onChange={(event) => setParseRunId(event.target.value)}
                placeholder="Parse Run ID"
                value={parseRunId}
              />
            </label>
            <Button className="mt-3 w-full" disabled={loading === "sync"} onClick={syncDocument} variant="primary">
              {loading === "sync" ? <Spinner /> : null}
              Add to Index
            </Button>
            {loading === "sync" ? (
              <p className="mt-3 font-mono text-xs text-[var(--text-muted)]">Embedding pages... (ColQwen2)</p>
            ) : null}
            {syncStatus ? <p className="mt-3 font-mono text-xs text-[var(--green)]">sync status: {syncStatus}</p> : null}
          </div>
          {error ? <ErrorBox message={error} /> : null}
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">Query</h2>
            <span className="font-mono text-xs text-[var(--text-muted)]">powered by ColQwen2 MaxSim</span>
          </div>
          <div className="mt-4 flex gap-2">
            <input
              className="h-10 min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--surface-3)] px-3 text-sm"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void runQuery();
                }
              }}
              placeholder="Ask anything about indexed documents..."
              value={query}
            />
            <Button disabled={loading === "query"} icon={loading === "query" ? <Spinner /> : <Search size={15} />} onClick={runQuery} variant="primary">
              Search
            </Button>
          </div>
          <div className="mt-5 grid gap-3">
            {hits.length ? (
              hits.map((hit, index) => (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4" key={`${hit.document_id}-${hit.page_num}-${index}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <Badge label={`#${index + 1}`} status="info" />
                      <h3 className="mt-2 font-mono text-sm">{hit.document_id}</h3>
                      <p className="text-sm text-[var(--text-secondary)]">Page {hit.page_num + 1}</p>
                    </div>
                    <span className="font-mono text-sm text-[var(--brand)]">{hit.score.toFixed(3)}</span>
                  </div>
                  <div className="mt-3">
                    <ScoreBar score={hit.score} />
                  </div>
                  <p className="mt-3 text-sm text-[var(--text-secondary)]">
                    Matching blocks: {hit.block_ids.length ? hit.block_ids.join(", ") : "visual page match"}
                  </p>
                  <details className="mt-3 text-xs text-[var(--text-muted)]">
                    <summary className="cursor-pointer">Score breakdown</summary>
                    <p className="mt-2 font-mono">Dense: {hit.score.toFixed(2)} | Sparse: 0.00 | Visual: {hit.score.toFixed(2)} | Rerank: --</p>
                  </details>
                  <Button className="mt-3" disabled={!hit.image_patch_path} onClick={() => void viewPage(hit)} variant="ghost">
                    View Page
                  </Button>
                </div>
              ))
            ) : (
              <div className="grid min-h-[420px] place-items-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--surface-2)] text-center">
                <div>
                  <i className="ti ti-search text-3xl text-[var(--text-muted)]" />
                  <p className="mt-3 text-sm text-[var(--text-secondary)]">Create a collection and sync parsed documents to start querying</p>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
      {pageUrl ? (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/75 p-5">
          <div className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-lg border border-[var(--border)] bg-[var(--surface-1)] p-3">
            <div className="mb-3 flex justify-end">
              <Button icon={<X size={14} />} onClick={() => setPageUrl(null)} variant="ghost">
                Close
              </Button>
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt="Indexed page render" className="mx-auto max-h-[80vh] w-auto rounded border border-[var(--border)]" src={pageUrl} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Header() {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] pb-4">
      <div>
        <h1 className="text-2xl font-medium">Index</h1>
        <p className="text-sm text-[var(--text-secondary)]">Build visual RAG collections and query rendered document pages</p>
      </div>
      <span className="font-mono text-[11px] text-[var(--text-muted)]">ws {getWorkspaceId().slice(0, 8)}</span>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <div className="mt-4 rounded-md border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] p-3 text-sm text-[var(--red)]">{message}</div>;
}
