const test = require("node:test");
const assert = require("node:assert/strict");

const { createMainWindowOptions } = require("../window-options");

test("macOS keeps the inset title bar used by the reference design", () => {
  const options = createMainWindowOptions("darwin", "/tmp/preload.js");

  assert.equal(options.titleBarStyle, "hiddenInset");
  assert.equal(options.titleBarOverlay, undefined);
  assert.equal(options.backgroundColor, "#09090b");
});

test("Windows uses a dark window-controls overlay without a menu bar", () => {
  const options = createMainWindowOptions("win32", "C:\\preload.js");

  assert.equal(options.titleBarStyle, "hidden");
  assert.equal(options.autoHideMenuBar, true);
  assert.deepEqual(options.titleBarOverlay, {
    color: "#09090b",
    symbolColor: "#f4f4f5",
    height: 48,
  });
});

test("both platforms share window dimensions and secure web preferences", () => {
  for (const platform of ["darwin", "win32"]) {
    const options = createMainWindowOptions(platform, "preload.js");

    assert.equal(options.width, 1280);
    assert.equal(options.height, 860);
    assert.deepEqual(options.webPreferences, {
      preload: "preload.js",
      contextIsolation: true,
      nodeIntegration: false,
    });
  }
});
