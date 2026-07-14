const WINDOW_BACKGROUND = "#09090b";
const WINDOW_FOREGROUND = "#f4f4f5";

function createMainWindowOptions(platform, preload) {
  const options = {
    width: 1280,
    height: 860,
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

module.exports = { createMainWindowOptions };
