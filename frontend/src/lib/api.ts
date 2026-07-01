/**
 * API client for the Memento backend.
 *
 * Base URL is configurable via NEXT_PUBLIC_API_BASE_URL, defaulting to the
 * local backend dev server.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Throw an Error carrying the backend's `detail` message when `res` is not OK.
 *
 * Backend (FastAPI HTTPException) always returns `{"detail":"..."}`. Falls
 * back to `<label> failed (HTTP <status>)` when the body is not JSON or has
 * no `detail` field. Network errors (fetch itself throwing) bypass this and
 * surface directly at call-site catch blocks.
 */
async function assertOk(res: Response, label: string): Promise<void> {
  if (res.ok) {
    return;
  }
  let detail: string | null = null;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string" && body.detail) {
      detail = body.detail;
    }
  } catch {
    // body is not JSON — detail stays null
  }
  throw new Error(detail ?? `${label} failed (HTTP ${res.status})`);
}

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
  await assertOk(res, "Health check");
  return res.json();
}

export async function listVideos(): Promise<VideoRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/videos`, { cache: "no-store" });
  await assertOk(res, "List videos");
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
  await assertOk(res, "Create video");
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
  await assertOk(res, "Process video");
  return res.json();
}

export async function deleteVideo(videoId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/videos/${videoId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 404) {
    await assertOk(res, "Delete video");
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
  await assertOk(res, "Check subtitles");
  return res.json();
}

export interface DocumentRecord {
  id: string;
  video_id: string | null;
  file_path: string;
  chunk_count: number;
  status: string;
  indexed_at: string | null;
  created_at: string | null;
  title: string;
  author: string;
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
  await assertOk(res, "List documents");
  return res.json();
}

export async function indexDocument(
  documentId: string
): Promise<DocumentRecord> {
  const res = await fetch(
    `${API_BASE_URL}/api/documents/${documentId}/index`,
    { method: "POST" }
  );
  await assertOk(res, "Index document");
  return res.json();
}

export async function previewChunks(
  documentId: string
): Promise<ChunkPreview[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/documents/${documentId}/chunks`,
    { cache: "no-store" }
  );
  await assertOk(res, "Preview chunks");
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
  await assertOk(res, "Delete document");
}

export async function cleanDocument(
  documentId: string
): Promise<DocumentRecord> {
  const res = await fetch(
    `${API_BASE_URL}/api/documents/${documentId}/clean`,
    { method: "POST" }
  );
  await assertOk(res, "Clean document");
  return res.json();
}

export interface UnimportedDocument {
  file_path: string;
  title: string | null;
  platform: string | null;
  source_url: string | null;
  video_id: string | null;
  author: string | null;
}

export async function listUnimportedDocuments(): Promise<UnimportedDocument[]> {
  const res = await fetch(`${API_BASE_URL}/api/documents/unimported`, {
    cache: "no-store",
  });
  await assertOk(res, "List unimported");
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
  await assertOk(res, "Import unimported");
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
    let detail: string | null = null;
    if (!res.ok) {
      try {
        const body = await res.json();
        if (typeof body?.detail === "string" && body.detail) {
          detail = body.detail;
        }
      } catch {
        // body is not JSON — detail stays null
      }
    }
    handlers.onError(detail ?? `Chat request failed: ${res.status}`);
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

// ===== Chat sessions =====

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export async function listSessions(): Promise<ChatSession[]> {
  const res = await fetch(`${API_BASE_URL}/api/sessions`);
  await assertOk(res, "List sessions");
  return res.json();
}

export async function createSession(title?: string): Promise<ChatSession> {
  const res = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(title ? { title } : {}),
  });
  await assertOk(res, "Create session");
  return res.json();
}

export async function getSessionMessages(
  sessionId: string
): Promise<ChatSessionMessage[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/messages`
  );
  await assertOk(res, "Get session messages");
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
  await assertOk(res, "Delete session");
  // 204 No Content — no body to parse.
}

export interface ModelConfig {
  provider: string | null;
  endpoint: string | null;
  api_key: string | null;
  model: string | null;
  protocol: "transcriptions" | "chat_audio" | null;
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

export async function updateModelSettings(
  payload: Partial<Record<keyof ModelsSettings, Partial<ModelConfig>>>
): Promise<ModelsSettings> {
  const res = await fetch(`${API_BASE_URL}/api/settings/models`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await assertOk(res, "Update settings");
  return res.json();
}

export async function getServiceStatus(): Promise<
  Record<string, ServiceStatus>
> {
  const res = await fetch(`${API_BASE_URL}/api/settings/status`, {
    cache: "no-store",
  });
  await assertOk(res, "Get status");
  return res.json();
}

export async function fetchApiKey(modelName: string): Promise<string | null> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/api_key`,
    { cache: "no-store" }
  );
  await assertOk(res, "Fetch api_key");
  const data = await res.json();
  return data.api_key;
}

export interface AsrDeployStatus {
  venv_exists: boolean;
  models_installed: boolean;
}

export interface AsrDeployProgress {
  stage: string;
  detail: string;
  percent: number | null;
  done: boolean;
  error: string | null;
}

export async function getAsrDeployStatus(): Promise<AsrDeployStatus> {
  const res = await fetch(`${API_BASE_URL}/api/asr/deploy/status`, {
    cache: "no-store",
  });
  await assertOk(res, "Get ASR deploy status");
  return res.json();
}

export async function deployAsr(): Promise<AsrDeployProgress> {
  const res = await fetch(`${API_BASE_URL}/api/asr/deploy`, {
    method: "POST",
  });
  await assertOk(res, "Deploy ASR");
  return res.json();
}

export async function getAsrDeployProgress(): Promise<AsrDeployProgress> {
  const res = await fetch(`${API_BASE_URL}/api/asr/deploy/progress`, {
    cache: "no-store",
  });
  await assertOk(res, "Get ASR deploy progress");
  return res.json();
}

// ── Local ASR Manager (model shelf) ──────────────────────────────────────────

export interface AsrEnvironment {
  venv_exists: boolean;
  service_python_exists: boolean;
  service_dir_exists: boolean;
  platform: string;
}

export interface AsrModelInfo {
  slug: string;
  family: string;
  label: string;
  model_id: string;
  spec: string | null;
  size: string;
  runtime: string;
  installed: boolean | null;
  installing: boolean;
  selected: boolean;
  estimated_size: string;
  cache_path: string | null;
  cache_paths_checked: string[];
  last_error: string | null;
}

export interface AsrDiskInfo {
  total: number;
  free: number;
  used: number;
}

export interface AsrManagerProgress {
  stage: string;
  model_slug: string | null;
  percent: number | null;
  detail: string | null;
  error: string | null;
  done: boolean;
}

export interface AsrManagerStatus {
  environment: AsrEnvironment;
  models: Record<string, AsrModelInfo>;
  current: string | null;
  disks: {
    service_disk: AsrDiskInfo;
    data_disk: AsrDiskInfo;
  };
  progress: AsrManagerProgress;
}

export async function getLocalAsrStatus(): Promise<AsrManagerStatus> {
  const res = await fetch(`${API_BASE_URL}/api/asr/local/status`, {
    cache: "no-store",
  });
  await assertOk(res, "Get local ASR status");
  return res.json();
}

export async function installLocalAsrModel(
  slug: string
): Promise<AsrManagerProgress> {
  const res = await fetch(`${API_BASE_URL}/api/asr/local/models/${slug}/install`, {
    method: "POST",
  });
  await assertOk(res, "Install local ASR model");
  return res.json();
}

export async function selectLocalAsrModel(
  slug: string
): Promise<{ current: string }> {
  const res = await fetch(`${API_BASE_URL}/api/asr/local/models/${slug}/select`, {
    method: "POST",
  });
  await assertOk(res, "Select local ASR model");
  return res.json();
}

export async function uninstallLocalAsrModel(
  slug: string
): Promise<AsrManagerProgress> {
  const res = await fetch(`${API_BASE_URL}/api/asr/local/models/${slug}`, {
    method: "DELETE",
  });
  await assertOk(res, "Uninstall local ASR model");
  return res.json();
}

export async function uninstallAllLocalAsr(): Promise<AsrManagerProgress> {
  const res = await fetch(`${API_BASE_URL}/api/asr/local/uninstall-all`, {
    method: "POST",
  });
  await assertOk(res, "Uninstall all local ASR");
  return res.json();
}

export async function getLocalAsrProgress(): Promise<AsrManagerProgress> {
  const res = await fetch(`${API_BASE_URL}/api/asr/local/progress`, {
    cache: "no-store",
  });
  await assertOk(res, "Get local ASR progress");
  return res.json();
}

// ── Model Presets ────────────────────────────────────────────────────────────

export interface PresetConfig {
  provider?: string | null;
  endpoint?: string | null;
  api_key?: string | null;
  model?: string | null;
  protocol?: string | null;
}

export interface PresetResponse {
  id: string;
  model_name: string;
  name: string;
  config: PresetConfig;
  created_at: string;
  updated_at: string;
}

export type PresetModelName = "chat" | "embedding" | "asr";

export async function listPresets(
  modelName: PresetModelName
): Promise<PresetResponse[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/presets`,
    { cache: "no-store" }
  );
  await assertOk(res, "List presets");
  return res.json();
}

export async function createPreset(
  modelName: PresetModelName,
  config: PresetConfig,
  name?: string
): Promise<PresetResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/presets`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, config }),
    }
  );
  await assertOk(res, "Create preset");
  return res.json();
}

export async function renamePreset(
  modelName: PresetModelName,
  presetId: string,
  newName: string
): Promise<PresetResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/presets/${presetId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    }
  );
  await assertOk(res, "Rename preset");
  return res.json();
}

export async function deletePreset(
  modelName: PresetModelName,
  presetId: string
): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/presets/${presetId}`,
    { method: "DELETE" }
  );
  await assertOk(res, "Delete preset");
}

export async function getActivePreset(
  modelName: PresetModelName
): Promise<{ preset_id: string | null; preset?: PresetResponse }> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/active`,
    { cache: "no-store" }
  );
  await assertOk(res, "Get active preset");
  return res.json();
}

export async function switchActivePreset(
  modelName: PresetModelName,
  presetId: string
): Promise<{ preset_id: string }> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/active`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset_id: presetId }),
    }
  );
  await assertOk(res, "Switch active preset");
  return res.json();
}

export async function updatePreset(
  modelName: PresetModelName,
  presetId: string,
  config: PresetConfig
): Promise<PresetResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/settings/models/${modelName}/presets/${presetId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config }),
    }
  );
  await assertOk(res, "Update preset");
  return res.json();
}

// ── Video Processing (Login) ─────────────────────────────────────────────────

export interface VideoProcessingSettings {
  bilibili_cookie: string;
  douyin_cookie: string;
  bilibili_refresh_token: string;
  bilibili_cookie_expires_at: number;
}

export interface VideoProcessingUpdate {
  bilibili_cookie?: string;
  douyin_cookie?: string;
  bilibili_refresh_token?: string;
  bilibili_cookie_expires_at?: number;
}

export async function getVideoProcessingSettings(): Promise<VideoProcessingSettings> {
  const res = await fetch(`${API_BASE_URL}/api/video-processing`, {
    cache: "no-store",
  });
  await assertOk(res, "Get video processing settings");
  return res.json();
}

export async function updateVideoProcessingSettings(
  payload: VideoProcessingUpdate
): Promise<VideoProcessingSettings> {
  const res = await fetch(`${API_BASE_URL}/api/video-processing`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await assertOk(res, "Update video processing settings");
  return res.json();
}
