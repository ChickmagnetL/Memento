const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const mainSource = fs.readFileSync(path.join(__dirname, "../main.js"), "utf8");
const preloadSource = fs.readFileSync(path.join(__dirname, "../preload.js"), "utf8");

test("packaged Windows keeps writable state under the install container", () => {
  const configurePathsAt = mainSource.indexOf("configurePackagedWindowsPaths();");
  const whenReadyAt = mainSource.indexOf("app.whenReady()");

  assert.match(
    mainSource,
    /function packagedInstallRoot\(\) \{\s*return path\.dirname\(path\.dirname\(app\.getPath\("exe"\)\)\);/,
  );
  assert.match(
    mainSource,
    /const electronDataDir = path\.join\(installRoot, "data", "electron"\);/,
  );
  assert.match(mainSource, /app\.setPath\("userData", electronDataDir\);/);
  assert.match(mainSource, /app\.setPath\("sessionData", electronDataDir\);/);
  assert.match(
    mainSource,
    /const dataDir = isPackagedWindows\(\)[\s\S]*?\? path\.join\(packagedInstallRoot\(\), "data", "storage"\)[\s\S]*?: path\.join\(app\.getPath\("userData"\), "data"\);/,
  );
  assert.match(
    mainSource,
    /function packagedRuntimeRoot\(\) \{\s*if \(isPackagedWindows\(\)\) \{\s*return packagedInstallRoot\(\);/,
  );
  assert.match(
    mainSource,
    /const projectRoot = isPackagedWindows\(\)\s*\? packagedInstallRoot\(\)/,
  );
  assert.ok(configurePathsAt >= 0);
  assert.ok(configurePathsAt < whenReadyAt);
});

test("packaged Windows tool caches stay under the install cache directory", () => {
  assert.match(
    mainSource,
    /const cacheRoot = path\.join\(installRoot, "cache"\);/,
  );
  assert.match(mainSource, /toolEnv\.PIP_CACHE_DIR = path\.join\(cacheRoot, "pip"\);/);
  assert.match(mainSource, /toolEnv\.UV_CACHE_DIR = path\.join\(cacheRoot, "uv"\);/);
  assert.match(mainSource, /toolEnv\.DENO_DIR = path\.join\(cacheRoot, "deno"\);/);
  assert.match(mainSource, /toolEnv\.TEMP = path\.join\(cacheRoot, "temp"\);/);
  assert.match(mainSource, /toolEnv\.TMP = path\.join\(cacheRoot, "temp"\);/);
  assert.match(mainSource, /toolEnv\.MODELSCOPE_CACHE = path\.join\(/);
  assert.match(mainSource, /toolEnv\.MOONSHINE_VOICE_CACHE = path\.join\(/);
});

test("main window is shown before packaged services are prepared", () => {
  const createWindowAt = mainSource.indexOf("window = new BrowserWindow");
  const showWindowAt = mainSource.indexOf("window.show()");
  const prepareRuntimeAt = mainSource.indexOf("preparePackagedRuntime();");

  assert.ok(createWindowAt >= 0);
  assert.ok(showWindowAt > createWindowAt);
  assert.ok(prepareRuntimeAt > showWindowAt);
  assert.match(mainSource, /await window\.loadURL\(STARTUP_PAGE_URL\)/);
  assert.match(mainSource, /await window\.loadURL\(FRONTEND_URL\)/);
});

test("desktop waits for the configured frontend before loading it", () => {
  const waitAt = mainSource.indexOf("await waitForFrontendHealth();");
  const loadAt = mainSource.indexOf("await window.loadURL(FRONTEND_URL);");

  assert.match(mainSource, /fetch\(FRONTEND_URL\)/);
  assert.ok(waitAt >= 0);
  assert.ok(loadAt > waitAt);
  assert.doesNotMatch(
    mainSource,
    /if \(isPackaged\(\)\) \{\s*await waitForFrontendHealth\(\);/,
  );
});

test("GitHub links open in the system browser through a fixed IPC action", () => {
  assert.match(mainSource, /const \{[\s\S]*?shell[\s\S]*?\} = require\("electron"\)/);
  assert.match(
    mainSource,
    /ipcMain\.handle\('open-github'[\s\S]*?shell\.openExternal\('https:\/\/github\.com\/ChickmagnetL\/Memento'\)/
  );
  assert.match(
    preloadSource,
    /openGitHub: \(\) => ipcRenderer\.invoke\('open-github'\)/
  );
});
