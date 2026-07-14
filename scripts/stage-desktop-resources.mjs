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

/**
 * fs.cpSync resolves relative symlinks to absolute paths when copying.
 * After copyDirectory, rewrite them back to relative so the app bundle is portable.
 */
function fixPyinstallerSymlinks(distDir) {
  const internalDir = path.join(distDir, "_internal");
  if (!fs.existsSync(internalDir)) {
    console.log(`  No _internal directory in ${distDir}, skipping symlink fix`);
    return;
  }
  const fwDir = path.join(internalDir, "Python.framework");
  if (!fs.existsSync(fwDir)) {
    console.log(`  No Python.framework in ${internalDir}, skipping symlink fix`);
    return;
  }
  const versionsDir = path.join(fwDir, "Versions");

  // 1. Find the version directory (e.g. "3.12")
  const entries = fs.readdirSync(versionsDir, { withFileTypes: true });
  const versionDir = entries.find((e) => e.isDirectory()).name;

  // 2. Fix Versions/Current -> <version>
  const currentLink = path.join(versionsDir, "Current");
  const currentTarget = fs.readlinkSync(currentLink);
  if (path.isAbsolute(currentTarget)) {
    fs.unlinkSync(currentLink);
    fs.symlinkSync(versionDir, currentLink);
  }

  // 3. Fix Python -> Versions/Current/Python
  const pythonLink = path.join(fwDir, "Python");
  const pythonTarget = fs.readlinkSync(pythonLink);
  if (path.isAbsolute(pythonTarget)) {
    fs.unlinkSync(pythonLink);
    fs.symlinkSync("Versions/Current/Python", pythonLink);
  }

  // 4. Fix Resources -> Versions/Current/Resources
  const resourcesLink = path.join(fwDir, "Resources");
  const resourcesTarget = fs.readlinkSync(resourcesLink);
  if (path.isAbsolute(resourcesTarget)) {
    fs.unlinkSync(resourcesLink);
    fs.symlinkSync("Versions/Current/Resources", resourcesLink);
  }

  // 5. Fix _internal/Python -> Python.framework/Versions/Current/Python
  const pythonBin = path.join(internalDir, "Python");
  if (fs.existsSync(pythonBin)) {
    const binTarget = fs.readlinkSync(pythonBin);
    if (path.isAbsolute(binTarget)) {
      fs.unlinkSync(pythonBin);
      fs.symlinkSync("Python.framework/Versions/Current/Python", pythonBin);
    }
  }

  console.log(`  Fixed PyInstaller symlinks in ${distDir}`);
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
fixPyinstallerSymlinks(path.join(resourcesDir, "backend"));

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
fixPyinstallerSymlinks(path.join(resourcesDir, "douyin-fetcher"));

for (const service of ["asr", "embedding", "node"]) {
  copyRuntimeService(service);
}

const ffmpegSource = require("ffmpeg-static");
const ffprobeSource = require("@ffprobe-installer/ffprobe").path;
const executableSuffix = process.platform === "win32" ? ".exe" : "";
const denoSource = path.join(
  path.dirname(require.resolve("deno/package.json")),
  `deno${executableSuffix}`,
);
const binDir = path.join(resourcesDir, "bin");
fs.mkdirSync(binDir, { recursive: true });
for (const [source, name] of [
  [ffmpegSource, `ffmpeg${executableSuffix}`],
  [ffprobeSource, `ffprobe${executableSuffix}`],
  [denoSource, `deno${executableSuffix}`],
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
