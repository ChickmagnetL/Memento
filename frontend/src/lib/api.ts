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

export type VideoStatus = "pending" | "processing" | "completed" | "failed";
export type VideoPlatform = "bilibili" | "douyin";

export interface VideoRecord {
  id: string;
  platform: VideoPlatform;
  title: string;
  author: string | null;
  duration: number | null;
  url: string;
  status: VideoStatus;
  created_at: string;
  processed_at: string | null;
}

export interface CreateVideoRequest {
  url: string;
  title?: string;
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

export async function listVideos(): Promise<VideoRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/videos`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`List videos failed: ${res.status}`);
  }
  return res.json();
}

export async function createVideo(
  payload: CreateVideoRequest
): Promise<VideoRecord> {
  const res = await fetch(`${API_BASE_URL}/api/videos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Create video failed: ${res.status}`);
  }
  return res.json();
}
