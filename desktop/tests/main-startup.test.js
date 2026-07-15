const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const mainSource = fs.readFileSync(path.join(__dirname, "../main.js"), "utf8");
const preloadSource = fs.readFileSync(path.join(__dirname, "../preload.js"), "utf8");

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
