/**
 * VideoPlayerManager - Manages video playback windows
 *
 * Opens independent BrowserWindow instances for playing videos.
 * Reuses windows per videoId to avoid duplicates.
 */

const { BrowserWindow, session } = require('electron');

const VIDEO_URL_BUILDERS = {
  bilibili: ({ videoId, timestamp }) => {
    const url = `https://www.bilibili.com/video/${videoId}`;
    return (timestamp && Number.isInteger(Number(timestamp)))
      ? `${url}?t=${timestamp}`
      : url;
  },
  douyin: ({ videoId }) => {
    return `https://www.douyin.com/video/${videoId}`;
  }
};

class VideoPlayerManager {
  constructor() {
    this.players = new Map();
  }

  open({ platform, videoId, timestamp, title }) {
    if (!VIDEO_URL_BUILDERS[platform]) {
      console.error(`[video-player] Unknown platform: ${platform}`);
      return;
    }

    const existingWindow = this.players.get(videoId);
    if (existingWindow && !existingWindow.isDestroyed()) {
      // If timestamp provided, navigate to it
      if (timestamp && platform === 'bilibili') {
        const url = VIDEO_URL_BUILDERS[platform]({ videoId, timestamp });
        existingWindow.webContents.loadURL(url);
      }
      existingWindow.focus();
      console.log(`[video-player] Focused existing window for ${videoId}`);
      return;
    }

    const playerSession = session.fromPartition(`persist:${platform}`, {
      cache: true
    });

    const displayTitle = title || videoId;

    const playerWindow = new BrowserWindow({
      width: 1280,
      height: 800,
      frame: false,
      title: displayTitle,
      webPreferences: {
        session: playerSession,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });

    const url = VIDEO_URL_BUILDERS[platform]({ videoId, timestamp });

    // Inject Memento title bar CSS after page loads
    playerWindow.webContents.on('did-finish-load', () => {
      playerWindow.webContents.insertCSS(`
        body {
          margin-top: 36px !important;
          overflow: auto !important;
        }
        #memento-titlebar {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          height: 36px;
          background: #1a1a2e;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 12px;
          -webkit-app-region: drag;
          z-index: 99999;
          user-select: none;
        }
        #memento-titlebar .title-text {
          color: #e0e0e0;
          font-size: 13px;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 60%;
        }
        #memento-titlebar .brand {
          color: #a78bfa;
          font-size: 13px;
          font-weight: 600;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          -webkit-app-region: no-drag;
        }
        #memento-titlebar .close-btn {
          -webkit-app-region: no-drag;
          cursor: pointer;
          color: #888;
          font-size: 18px;
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
        }
        #memento-titlebar .close-btn:hover {
          color: #fff;
          background: #e81123;
        }
      `);

      playerWindow.webContents.executeJavaScript(`
        if (!document.getElementById('memento-titlebar')) {
          const bar = document.createElement('div');
          bar.id = 'memento-titlebar';
          bar.innerHTML = \`
            <span class="brand">Memento</span>
            <span class="title-text">${displayTitle.replace(/'/g, "\\'")}</span>
            <span class="close-btn" id="memento-close-btn">×</span>
          \`;
          document.body.prepend(bar);
          document.getElementById('memento-close-btn').addEventListener('click', () => {
            window.close();
          });
        }
      `);
    });

    playerWindow.loadURL(url).catch(err => {
      console.error(`[video-player] Failed to load ${url}:`, err);
      playerWindow.close();
    });

    this.players.set(videoId, playerWindow);

    playerWindow.on('closed', () => {
      this.players.delete(videoId);
      console.log(`[video-player] Window closed for ${videoId}`);
    });

    console.log(`[video-player] Opened ${platform} video: ${videoId}`);
  }

  closeAll() {
    for (const [videoId, window] of this.players.entries()) {
      try {
        if (!window.isDestroyed()) {
          window.close();
        }
      } catch (err) {
        console.warn(`[video-player] Failed to close window for ${videoId}:`, err);
      }
    }
    this.players.clear();
    console.log('[video-player] Closed all player windows');
  }
}

module.exports = { VideoPlayerManager };
