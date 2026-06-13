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

export async function processVideo(videoId: string): Promise<VideoRecord> {
  const res = await fetch(`${API_BASE_URL}/api/videos/${videoId}/process`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Process video failed: ${res.status}`);
  }
  return res.json();
}

export interface DocumentRecord {
  id: string;
  video_id: string;
  file_path: string;
  chunk_count: number;
  is_indexed: boolean;
  indexed_at: string | null;
}

export interface ChunkPreview {
  chunk_index: number;
  title_path: string;
  text: string;
  start_timestamp: string | null;
}

export async function listDocuments(): Promise<DocumentRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/documents`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`List documents failed: ${res.status}`);
  }
  return res.json();
}

export async function indexDocument(
  documentId: string
): Promise<DocumentRecord> {
  const res = await fetch(
    `${API_BASE_URL}/api/documents/${documentId}/index`,
    { method: "POST" }
  );
  if (!res.ok) {
    throw new Error(`Index document failed: ${res.status}`);
  }
  return res.json();
}

export async function previewChunks(
  documentId: string
): Promise<ChunkPreview[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/documents/${documentId}/chunks`,
    { cache: "no-store" }
  );
  if (!res.ok) {
    throw new Error(`Preview chunks failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/documents/${documentId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Delete document failed: ${res.status}`);
  }
}

export async function cleanDocument(
  documentId: string
): Promise<DocumentRecord> {
  const res = await fetch(
    `${API_BASE_URL}/api/documents/${documentId}/clean`,
    { method: "POST" }
  );
  if (!res.ok) {
    throw new Error(`Clean document failed: ${res.status}`);
  }
  return res.json();
}

export interface ChatStreamHandlers {
  onDelta: (delta: string) => void;
  onDone: (sessionId: string) => void;
  onError: (message: string) => void;
}

/**
 * Send one chat turn and consume the SSE stream.
 *
 * The backend emits `data: {...}` lines with events:
 * {type:"text",delta} / {type:"done",session_id} / {type:"error",message}.
 */
export async function sendChatMessage(
  message: string,
  sessionId: string | null,
  handlers: ChatStreamHandlers
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      sessionId ? { message, session_id: sessionId } : { message }
    ),
  });
  if (!res.ok || !res.body) {
    handlers.onError(`Chat request failed: ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const rawEvent of events) {
        const dataLine = rawEvent
          .split("\n")
          .find((line) => line.startsWith("data: "));
        if (!dataLine) {
          continue;
        }
        try {
          const event = JSON.parse(dataLine.slice("data: ".length));
          if (event.type === "text") {
            handlers.onDelta(event.delta);
          } else if (event.type === "done") {
            handlers.onDone(event.session_id);
          } else if (event.type === "error") {
            handlers.onError(event.message);
          }
        } catch {
          handlers.onError("Chat request failed: invalid event");
        }
      }
    }
  } catch {
    handlers.onError("Chat request failed: connection lost");
  }
}
