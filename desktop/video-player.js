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
      height: 900,
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

    playerWindow.webContents.on('did-finish-load', () => {
      playerWindow.webContents.executeJavaScript(`
        if (!document.getElementById('memento-titlebar')) {
          const style = document.createElement('style');
          style.textContent = \`
            body { margin-top: 36px !important; overflow: auto !important; }
            #memento-titlebar {
              position: fixed; top: 0; left: 0; right: 0; height: 36px;
              background: #1a1a2e; display: flex; align-items: center;
              justify-content: space-between; padding: 0 12px;
              -webkit-app-region: drag; z-index: 99999; user-select: none;
            }
            #memento-titlebar .title-text {
              color: #e0e0e0; font-size: 13px;
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 60%;
            }
            #memento-titlebar .brand {
              color: #a78bfa; font-size: 13px; font-weight: 600;
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              -webkit-app-region: no-drag;
            }
            #memento-titlebar .close-btn {
              -webkit-app-region: no-drag; cursor: pointer; color: #888;
              font-size: 18px; width: 28px; height: 28px;
              display: flex; align-items: center; justify-content: center; border-radius: 4px;
            }
            #memento-titlebar .close-btn:hover { color: #fff; background: #e81123; }
          \`;
          document.head.appendChild(style);

          const bar = document.createElement('div');
          bar.id = 'memento-titlebar';

          const brand = document.createElement('span');
          brand.className = 'brand';
          brand.textContent = 'Memento';

          const title = document.createElement('span');
          title.className = 'title-text';
          title.textContent = ${JSON.stringify(displayTitle)};

          const closeBtn = document.createElement('span');
          closeBtn.className = 'close-btn';
          closeBtn.textContent = '\\u00d7';
          closeBtn.addEventListener('click', () => {
            window.close();
          });

          bar.appendChild(brand);
          bar.appendChild(title);
          bar.appendChild(closeBtn);
          document.body.prepend(bar);
        }

        // Bilibili: hide non-player elements
        if ('${platform}' === 'bilibili' && !document.getElementById('memento-bilibili-style')) {
          const bilibiliStyle = document.createElement('style');
          bilibiliStyle.id = 'memento-bilibili-style';
          bilibiliStyle.textContent = \`
            /* Hide header/navigation */
            .bili-header, #biliMainHeader, .mini-header,
            .bili-header__bar, .v-wrap, .z-top-container {
              display: none !important;
            }

            /* Hide comments section */
            #comment, .comment-container, .reply-list,
            .comment-list, .bili-comment-container {
              display: none !important;
            }

            /* Hide recommended videos sidebar */
            .video-card-box, .rec-list, .right-container,
            .video-page-card-small, .rcmd-list {
              display: none !important;
            }

            /* Hide user info area */
            .upinfo, .member-info, .up-info,
            .user-info, .author-info {
              display: none !important;
            }

            /* Hide footer and other non-player chrome */
            footer, .footer, .bili-footer,
            .video-toolbar, .toolbar,
            .video-desc, .desc-info,
            .video-tag, .tag-container,
            .video-state, .video-data {
              display: none !important;
            }

            /* Ensure player fills available space */
            .bpx-player-container, #bilibili-player, .player-wrap {
              display: block !important;
            }
          \`;
          document.head.appendChild(bilibiliStyle);
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
