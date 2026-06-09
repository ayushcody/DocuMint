export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? process.env.NEXT_PUBLIC_DOCUMIND_API_URL ?? "http://localhost:8000";

export const DEFAULT_WORKSPACE_ID =
  process.env.NEXT_PUBLIC_WORKSPACE_ID ??
  process.env.NEXT_PUBLIC_DOCUMIND_WORKSPACE_ID ??
  "00000000-0000-0000-0000-000000000001";

export function getWorkspaceId(): string {
  if (typeof window === "undefined") {
    return DEFAULT_WORKSPACE_ID;
  }
  return (
    window.localStorage.getItem("workspace_id") ??
    window.localStorage.getItem("documind_workspace_id") ??
    DEFAULT_WORKSPACE_ID
  );
}

export function getBearerToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem("documind_api_token");
}
