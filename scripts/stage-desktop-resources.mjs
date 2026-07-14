#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const desktopDir = path.join(root, "desktop");
const resourcesDir = path.join(desktopDir, "resources");
const require = createRequire(path.join(desktopDir, "package.json"));

function copyDirectory(source, target, options = {}) {
  if (!fs.existsSync(source)) {
    throw new Error(`Missing build resource: ${source}`);
  }
  fs.cpSync(source, target, { recursive: true, force: true, ...options });
}

function copyRuntimeService(name) {
  const source = path.join(root, "services", name);
  const target = path.join(resourcesDir, "services", name);
  const excluded = new Set([
    ".venv",
    ".packaging-venv",
    "__pycache__",
    "dist",
    "build",
    "logs",
    "models",
    "tests",
  ]);
  copyDirectory(source, target, {
    filter: (entry) => {
      const relative = path.relative(source, entry);
      return !relative.split(path.sep).some((part) => excluded.has(part));
    },
  });
}

fs.rmSync(resourcesDir, { recursive: true, force: true });
fs.mkdirSync(resourcesDir, { recursive: true });

copyDirectory(
  path.join(root, "backend", "dist", "memento-backend"),
  path.join(resourcesDir, "backend"),
);
copyDirectory(
  path.join(root, "frontend", ".next", "standalone"),
  path.join(resourcesDir, "frontend"),
);

const frontendModules = path.join(resourcesDir, "frontend", "node_modules");
fs.renameSync(frontendModules, path.join(resourcesDir, "frontend", "node_deps"));

copyDirectory(
  path.join(root, "services", "douyin_fetcher", "dist", "memento-douyin-fetcher"),
  path.join(resourcesDir, "douyin-fetcher"),
);

for (const service of ["asr", "embedding", "node"]) {
  copyRuntimeService(service);
}

const ffmpegSource = require("ffmpeg-static");
const ffprobeSource = require("@ffprobe-installer/ffprobe").path;
const executableSuffix = process.platform === "win32" ? ".exe" : "";
const binDir = path.join(resourcesDir, "bin");
fs.mkdirSync(binDir, { recursive: true });
for (const [source, name] of [
  [ffmpegSource, `ffmpeg${executableSuffix}`],
  [ffprobeSource, `ffprobe${executableSuffix}`],
]) {
  if (!source || !fs.existsSync(source)) {
    throw new Error(`Missing ${name} dependency for ${process.platform}`);
  }
  const target = path.join(binDir, name);
  fs.copyFileSync(source, target);
  if (process.platform !== "win32") {
    fs.chmodSync(target, 0o755);
  }
}

console.log(`Desktop resources staged at ${resourcesDir}`);
