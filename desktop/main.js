/**
 * Memento desktop shell.
 *
 * Spawns the packaged backend, waits for /health, then opens a window
 * pointing at the frontend URL. Dev mode: frontend runs separately
 * (npm run dev) and the backend can be overridden via env vars.
 */

const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const { LoginWindowManager } = require("./login-manager");
const { VideoPlayerManager } = require("./video-player");
const { CookieRefreshScheduler } = require("./cookie-refresh");

const FRONTEND_PORT = 3123;
const FRONTEND_URL =
  process.env.MEMENTO_FRONTEND_URL ||
  (isPackaged() ? `http://localhost:${FRONTEND_PORT}` : "http://localhost:3000");
const BACKEND_HEALTH_URL = "http://localhost:8000/api/health";
const DOUYIN_FETCHER_HEALTH_URL = "http://127.0.0.1:8002/health";

function isPackaged() {
  return app.isPackaged;
}

function dataDirEnv() {
  if (!isPackaged()) {
    return {};
  }
  return { STORAGE__DATA_DIR: path.join(app.getPath("userData"), "data") };
}

let backendProcess = null;
let douyinFetcherProcess = null;
let videoPlayerManager = null;
let cookieRefreshScheduler = null;
let mainWindow = null;
let isQuitting = false;

function resolveBackendEnv() {
  const projectRoot = process.env.MEMENTO_PROJECT_ROOT || path.join(__dirname, "..");
  return {
    ...process.env,
    MEMENTO_PROJECT_ROOT: projectRoot,
    ...dataDirEnv(),
  };
}

function resolveBackendCommand() {
  // Dev override, e.g. MEMENTO_BACKEND_CMD="../backend/venv/bin/uvicorn main:app"
  if (process.env.MEMENTO_BACKEND_CMD) {
    const [command, ...args] = process.env.MEMENTO_BACKEND_CMD.split(" ");
    return { command, args, cwd: path.join(__dirname, "..", "backend") };
  }
  if (isPackaged()) {
    const binary = path.join(
      process.resourcesPath, "backend", "memento-backend",
      process.platform === "win32" ? "memento-backend.exe" : "memento-backend"
    );
    return { command: binary, args: [], cwd: path.dirname(binary) };
  }
  const binary = path.join(
    __dirname, "..", "backend", "dist", "memento-backend", "memento-backend"
  );
  return { command: binary, args: [], cwd: path.dirname(binary) };
}

function resolveDouyinFetcherCommand() {
  const serviceDir = path.join(__dirname, "..", "services", "douyin_fetcher");
  if (process.env.MEMENTO_DOUYIN_FETCHER_CMD) {
    const [command, ...args] = process.env.MEMENTO_DOUYIN_FETCHER_CMD.split(" ");
    return { command, args, cwd: serviceDir };
  }
  const uvicorn = path.join(serviceDir, ".venv", "bin", "uvicorn");
  if (!fs.existsSync(uvicorn)) {
    console.warn(
      `[douyin-fetcher] Not started: ${uvicorn} is missing. Run services/douyin_fetcher/setup.sh to enable Douyin desktop processing.`
    );
    return null;
  }
  return {
    command: uvicorn,
    args: ["server:app", "--host", "127.0.0.1", "--port", "8002"],
    cwd: serviceDir,
  };
}

async function isBackendHealthy() {
  try {
    const response = await Promise.race([
      fetch(BACKEND_HEALTH_URL),
      new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 1000)),
    ]);
    return response.ok;
  } catch {
    return false;
  }
}

async function startBackend() {
  if (await isBackendHealthy()) {
    console.log("[backend] Already healthy on localhost:8000; not spawning another process.");
    return;
  }
  const { command, args, cwd } = resolveBackendCommand();
  backendProcess = spawn(command, args, {
    cwd,
    env: resolveBackendEnv(),
    stdio: ["ignore", "pipe", "pipe"],
  });
  backendProcess.stdout.on("data", (d) => process.stdout.write(`[backend] ${d}`));
  backendProcess.stderr.on("data", (d) => process.stderr.write(`[backend] ${d}`));
  backendProcess.on("exit", (code) => {
    backendProcess = null;
    if (code !== 0 && code !== null) {
      dialog.showErrorBox("Memento", `Backend exited with code ${code}`);
      app.quit();
    }
  });
}

async function isDouyinFetcherHealthy() {
  try {
    const response = await Promise.race([
      fetch(DOUYIN_FETCHER_HEALTH_URL),
      new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 1000)),
    ]);
    return response.ok;
  } catch {
    return false;
  }
}

async function startDouyinFetcher() {
  if (await isDouyinFetcherHealthy()) {
    console.log("[douyin-fetcher] Already healthy on 127.0.0.1:8002; not spawning another process.");
    return;
  }

  const commandConfig = resolveDouyinFetcherCommand();
  if (!commandConfig) {
    return;
  }

  const { command, args, cwd } = commandConfig;
  douyinFetcherProcess = spawn(command, args, {
    cwd,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  douyinFetcherProcess.stdout.on("data", (d) => process.stdout.write(`[douyin-fetcher] ${d}`));
  douyinFetcherProcess.stderr.on("data", (d) => process.stderr.write(`[douyin-fetcher] ${d}`));
  douyinFetcherProcess.on("error", (error) => {
    console.warn(`[douyin-fetcher] Failed to start: ${error.message}`);
    douyinFetcherProcess = null;
  });
  douyinFetcherProcess.on("exit", (code) => {
    douyinFetcherProcess = null;
    if (code !== 0 && code !== null) {
      console.warn(`[douyin-fetcher] Exited with code ${code}`);
    }
  });
}

async function waitForHealth(timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(BACKEND_HEALTH_URL);
      if (response.ok) {
        return;
      }
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("Backend did not become healthy in time");
}

async function waitForFrontendHealth(timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://localhost:${FRONTEND_PORT}`);
      if (response.ok) {
        return;
      }
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("Frontend did not become healthy in time");
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

let frontendProcess = null;

function startFrontend() {
  if (!isPackaged()) {
    console.log("[frontend] Dev mode, skipping packaged frontend server.");
    return;
  }
  console.log("[frontend] Starting packaged frontend server...");
  const serverJs = path.join(
    process.resourcesPath, "frontend", "server.js"
  );
  frontendProcess = spawn(process.execPath, [serverJs], {
    cwd: path.dirname(serverJs),
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: "1",
      PORT: String(FRONTEND_PORT),
      HOSTNAME: "127.0.0.1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  frontendProcess.stdout.on("data", (d) => process.stdout.write(`[frontend] ${d}`));
  frontendProcess.stderr.on("data", (d) => process.stderr.write(`[frontend] ${d}`));
  frontendProcess.on("error", (error) => {
    console.warn(`[frontend] Failed to start: ${error.message}`);
    frontendProcess = null;
  });
  frontendProcess.on("exit", (code) => {
    frontendProcess = null;
    if (code !== 0 && code !== null) {
      console.warn(`[frontend] Exited with code ${code}`);
    }
  });
}

function stopFrontend() {
  if (frontendProcess) {
    frontendProcess.kill();
    frontendProcess = null;
  }
}

function stopDouyinFetcher() {
  if (douyinFetcherProcess) {
    douyinFetcherProcess.kill();
    douyinFetcherProcess = null;
  }
}

function stopSidecars() {
  stopFrontend();
  stopDouyinFetcher();
  stopBackend();
}

async function loadBilibiliRefreshToken() {
  try {
    const res = await fetch("http://127.0.0.1:8000/api/video-processing");
    if (!res.ok) return;
    const data = await res.json();
    if (data.bilibili_refresh_token) {
      cookieRefreshScheduler.setRefreshToken(data.bilibili_refresh_token);
    }
  } catch (e) {
    console.warn(
      "[main] Failed to load bilibili_refresh_token:",
      e && e.message ? e.message : e
    );
  }
}

app.whenReady().then(async () => {
  await startDouyinFetcher();
  await startBackend();
  await startFrontend();
  try {
    await waitForHealth();
    if (isPackaged()) {
      await waitForFrontendHealth();
    }
  } catch (error) {
    dialog.showErrorBox("Memento", String(error));
    stopSidecars();
    app.quit();
    return;
  }
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    }
  });
  mainWindow = window;
  window.loadURL(FRONTEND_URL);

  const loginManager = new LoginWindowManager(window);
  videoPlayerManager = new VideoPlayerManager();
  cookieRefreshScheduler = new CookieRefreshScheduler({
    getMainWindow: () => mainWindow,
  });
  await loadBilibiliRefreshToken();
  cookieRefreshScheduler.start();

  window.on('close', () => {
    if (loginManager) {
      loginManager.close();
    }
  });

  ipcMain.on('open-login', (event, platform) => {
    if (platform !== 'bilibili' && platform !== 'douyin') {
      console.error(`[main] Invalid platform: ${platform}`);
      return;
    }
    console.log(`[main] Received open-login request for ${platform}`);
    loginManager.open(platform);
  });

  ipcMain.handle('clear-login-session', async (event, platform) => {
    if (platform !== 'bilibili' && platform !== 'douyin') {
      console.error(`[main] Invalid platform: ${platform}`);
      return;
    }
    console.log(`[main] Clearing session for ${platform}`);
    const { session } = require('electron');
    const platformSession = session.fromPartition(`persist:${platform}`);
    await platformSession.clearStorageData();
    console.log(`[main] Session cleared for ${platform}`);
  });

  ipcMain.handle('refresh-bilibili-cookie', async () => {
    if (!cookieRefreshScheduler) {
      return { ok: false, refreshed: false, reason: 'unavailable' };
    }
    return cookieRefreshScheduler.refreshIfNeeded();
  });

  ipcMain.on('open-video-player', (event, params) => {
    const { platform, videoId, timestamp, title } = params;
    if (platform !== 'bilibili' && platform !== 'douyin') {
      console.error(`[main] Invalid platform: ${platform}`);
      return;
    }
    if (!videoId) {
      console.error(`[main] Missing videoId`);
      return;
    }
    console.log(`[main] Opening video player: ${platform} ${videoId} ${timestamp || 'no timestamp'}`);
    videoPlayerManager.open({ platform, videoId, timestamp, title });
  });
});

app.on("window-all-closed", () => {
  if (isQuitting) return;
  isQuitting = true;
  stopSidecars();
  app.quit();
});

app.on("before-quit", () => {
  isQuitting = true;
  stopSidecars();
  if (videoPlayerManager) {
    videoPlayerManager.closeAll();
  }
  if (cookieRefreshScheduler) {
    cookieRefreshScheduler.stop();
  }
});
