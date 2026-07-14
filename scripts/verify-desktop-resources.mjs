#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const resourcesDir = path.resolve(process.argv[2] || "desktop/resources");
const executableSuffix = process.platform === "win32" ? ".exe" : "";
const required = [
  path.join("backend", `memento-backend${executableSuffix}`),
  path.join("frontend", "server.js"),
  path.join("frontend", "node_deps"),
  path.join("douyin-fetcher", `memento-douyin-fetcher${executableSuffix}`),
  path.join("bin", `ffmpeg${executableSuffix}`),
  path.join("bin", `ffprobe${executableSuffix}`),
  path.join("services", "asr", "deploy.py"),
  path.join("services", "asr", "server.py"),
  path.join("services", "embedding", "deploy.py"),
  path.join("services", "node", "node_app", "toolchain.py"),
];

for (const relative of required) {
  const target = path.join(resourcesDir, relative);
  if (!fs.existsSync(target)) {
    throw new Error(`Required desktop resource is missing: ${target}`);
  }
}

for (const tool of [`ffmpeg${executableSuffix}`, `ffprobe${executableSuffix}`]) {
  const target = path.join(resourcesDir, "bin", tool);
  const result = spawnSync(target, ["-version"], { encoding: "utf8" });
  if (result.status !== 0) {
    throw new Error(`${tool} cannot run: ${result.stderr || result.error}`);
  }
}

console.log(`Desktop runtime resources verified at ${resourcesDir}`);
