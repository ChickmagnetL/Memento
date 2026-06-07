/**
 * API client for the Memento backend.
 *
 * Base URL is configurable via NEXT_PUBLIC_API_BASE_URL, defaulting to the
 * local backend dev server.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  service: string;
}

/**
 * Fetch backend health status.
 *
 * @throws Error if the request fails (non-2xx response).
 */
export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}
