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
  author_id: string | null;
  duration: number | null;
  url: string;
  status: VideoStatus;
  error_message: string | null;
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

export async function processVideo(
  videoId: string,
  fallback?: "asr"
): Promise<VideoRecord> {
  const qs = fallback ? `?subtitle_fallback=${fallback}` : "";
  const res = await fetch(`${API_BASE_URL}/api/videos/${videoId}/process${qs}`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Process video failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteVideo(videoId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/videos/${videoId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 404) {
    throw new Error(`Delete video failed: ${res.status}`);
  }
}

export interface SubtitleCheckResult {
  has_subtitles: boolean;
  platform: string;
}

export async function checkSubtitles(
  videoId: string
): Promise<SubtitleCheckResult> {
  const res = await fetch(
    `${API_BASE_URL}/api/videos/${videoId}/check-subtitles`,
    { cache: "no-store" }
  );
  if (!res.ok) {
    throw new Error(`Check subtitles failed: ${res.status}`);
  }
  return res.json();
}

export interface DocumentRecord {
  id: string;
  video_id: string | null;
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

export async function deleteDocument(
  documentId: string,
  deleteSourceFile = false
): Promise<void> {
  const qs = deleteSourceFile ? "?delete_source_file=true" : "";
  const res = await fetch(`${API_BASE_URL}/api/documents/${documentId}${qs}`, {
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

export interface UnimportedDocument {
  file_path: string;
  title: string | null;
  platform: string | null;
  source_url: string | null;
  video_id: string | null;
}

export async function listUnimportedDocuments(): Promise<UnimportedDocument[]> {
  const res = await fetch(`${API_BASE_URL}/api/documents/unimported`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`List unimported failed: ${res.status}`);
  }
  return res.json();
}

export async function importUnimportedDocuments(
  filePaths: string[]
): Promise<DocumentRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/documents/unimported/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_paths: filePaths }),
  });
  if (!res.ok) {
    throw new Error(`Import unimported failed: ${res.status}`);
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

export interface ModelConfig {
  provider: string | null;
  endpoint: string | null;
  api_key: string | null;
  model: string | null;
}

export interface ModelsSettings {
  chat: ModelConfig;
  embedding: ModelConfig;
  asr: ModelConfig;
}

export interface ServiceStatus {
  status: string;
  endpoint?: string;
}

export async function getModelSettings(): Promise<ModelsSettings> {
  const res = await fetch(`${API_BASE_URL}/api/settings/models`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Get settings failed: ${res.status}`);
  }
  return res.json();
}

export async function updateModelSettings(
  payload: Partial<Record<keyof ModelsSettings, Partial<ModelConfig>>>
): Promise<ModelsSettings> {
  const res = await fetch(`${API_BASE_URL}/api/settings/models`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Update settings failed: ${res.status}`);
  }
  return res.json();
}

export async function getServiceStatus(): Promise<
  Record<string, ServiceStatus>
> {
  const res = await fetch(`${API_BASE_URL}/api/settings/status`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Get status failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchApiKey(modelName: string): Promise<string | null> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/api_key`,
    { cache: "no-store" }
  );
  if (!res.ok) {
    throw new Error(`Fetch api_key failed: ${res.status}`);
  }
  const data = await res.json();
  return data.api_key;
}
