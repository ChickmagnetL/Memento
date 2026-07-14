const WINDOW_BACKGROUND = "#09090b";
const WINDOW_FOREGROUND = "#f4f4f5";
const STARTUP_PAGE_URL = `data:text/html;charset=UTF-8,${encodeURIComponent(`<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <style>
      html, body { height: 100%; margin: 0; }
      body {
        display: grid;
        place-items: center;
        background: ${WINDOW_BACKGROUND};
        color: ${WINDOW_FOREGROUND};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      main { text-align: center; }
      h1 { margin: 0; font-size: 28px; font-weight: 650; }
      p { margin: 12px 0 0; color: #a1a1aa; font-size: 14px; }
    </style>
  </head>
  <body>
    <main>
      <h1>Memento</h1>
      <p>Starting local services…</p>
    </main>
  </body>
</html>`)}`;

function createMainWindowOptions(platform, preload) {
  const options = {
    width: 1280,
    height: 860,
    show: false,
    backgroundColor: WINDOW_BACKGROUND,
    webPreferences: {
      preload,
      contextIsolation: true,
      nodeIntegration: false,
    },
  };

  if (platform === "darwin") {
    return {
      ...options,
      titleBarStyle: "hiddenInset",
    };
  }

  if (platform === "win32") {
    return {
      ...options,
      titleBarStyle: "hidden",
      titleBarOverlay: {
        color: WINDOW_BACKGROUND,
        symbolColor: WINDOW_FOREGROUND,
        height: 48,
      },
      autoHideMenuBar: true,
    };
  }

  return options;
}

module.exports = { createMainWindowOptions, STARTUP_PAGE_URL };
