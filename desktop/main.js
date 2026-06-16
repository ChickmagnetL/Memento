/**
 * Memento desktop shell.
 *
 * Spawns the packaged backend, waits for /health, then opens a window
 * pointing at the frontend URL. Dev mode: frontend runs separately
 * (npm run dev) and the backend can be overridden via env vars.
 */

const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const FRONTEND_URL =
  process.env.MEMENTO_FRONTEND_URL || "http://localhost:3000";
const BACKEND_HEALTH_URL = "http://localhost:8000/api/health";

let backendProcess = null;

function resolveBackendCommand() {
  // Dev override, e.g. MEMENTO_BACKEND_CMD="../backend/venv/bin/uvicorn main:app"
  if (process.env.MEMENTO_BACKEND_CMD) {
    const [command, ...args] = process.env.MEMENTO_BACKEND_CMD.split(" ");
    return { command, args, cwd: path.join(__dirname, "..", "backend") };
  }
  const binary = path.join(
    __dirname, "..", "backend", "dist", "memento-backend", "memento-backend"
  );
  return { command: binary, args: [], cwd: path.dirname(binary) };
}

function startBackend() {
  const { command, args, cwd } = resolveBackendCommand();
  backendProcess = spawn(command, args, {
    cwd,
    env: { ...process.env },
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

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForHealth();
  } catch (error) {
    dialog.showErrorBox("Memento", String(error));
    stopBackend();
    app.quit();
    return;
  }
  const window = new BrowserWindow({ width: 1280, height: 860 });
  window.loadURL(FRONTEND_URL);
});

app.on("window-all-closed", () => {
  stopBackend();
  app.quit();
});

app.on("before-quit", stopBackend);
