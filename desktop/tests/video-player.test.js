const test = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const Module = require("node:module");
const { join } = require("node:path");

const originalLoad = Module._load;
Module._load = (request, parent, isMain) =>
  request === "electron" ? {} : originalLoad(request, parent, isMain);
const {
  VIDEO_URL_BUILDERS,
  VideoPlayerManager,
  handlePlayerLoadFailure,
} = require("../video-player");
Module._load = originalLoad;

test("video player IPC accepts YouTube without adding YouTube login", () => {
  const mainSource = readFileSync(join(__dirname, "../main.js"), "utf8");
  assert.match(
    mainSource,
    /open-video-player[\s\S]*platform !== 'bilibili' && platform !== 'douyin' && platform !== 'youtube'/
  );
  assert.match(
    mainSource,
    /open-login[\s\S]*platform !== 'bilibili' && platform !== 'douyin'/
  );
  assert.doesNotMatch(
    mainSource,
    /open-login[\s\S]{0,200}platform !== 'youtube'/
  );
});

test("YouTube URL includes the requested start time", () => {
  assert.equal(
    VIDEO_URL_BUILDERS.youtube({ videoId: "dQw4w9WgXcQ", timestamp: 83 }),
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=83s"
  );
});

test("existing YouTube window navigates to a new timestamp", () => {
  const manager = new VideoPlayerManager(null);
  const loadedUrls = [];
  let focused = false;
  manager.players.set("dQw4w9WgXcQ", {
    isDestroyed: () => false,
    webContents: {
      loadURL: (url) => loadedUrls.push(url),
    },
    focus: () => {
      focused = true;
    },
  });

  manager.open({
    platform: "youtube",
    videoId: "dQw4w9WgXcQ",
    timestamp: 125,
  });

  assert.deepEqual(loadedUrls, [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=125s",
  ]);
  assert.equal(focused, true);
});

test("YouTube redirect abort does not close the player window", () => {
  let closed = false;
  const playerWindow = {
    isDestroyed: () => false,
    close: () => {
      closed = true;
    },
  };

  handlePlayerLoadFailure(
    playerWindow,
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=83s",
    { code: "ERR_ABORTED", errno: -3 }
  );

  assert.equal(closed, false);
});

test("existing YouTube timestamp navigation handles redirect abort", async () => {
  const manager = new VideoPlayerManager(null);
  let closed = false;
  manager.players.set("dQw4w9WgXcQ", {
    isDestroyed: () => false,
    webContents: {
      loadURL: () => Promise.reject({ code: "ERR_ABORTED", errno: -3 }),
    },
    focus: () => {},
    close: () => {
      closed = true;
    },
  });

  manager.open({
    platform: "youtube",
    videoId: "dQw4w9WgXcQ",
    timestamp: 125,
  });
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(closed, false);
});

test("fatal player load failure still closes the player window", () => {
  let closed = false;
  const playerWindow = {
    isDestroyed: () => false,
    close: () => {
      closed = true;
    },
  };

  handlePlayerLoadFailure(playerWindow, "https://example.invalid", {
    code: "ERR_NAME_NOT_RESOLVED",
    errno: -105,
  });

  assert.equal(closed, true);
});
