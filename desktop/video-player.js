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
    return timestamp ? `${url}?t=${timestamp}` : url;
  },
  douyin: ({ videoId }) => {
    return `https://www.douyin.com/video/${videoId}`;
  }
};

class VideoPlayerManager {
  constructor() {
    this.players = new Map();
  }

  open({ platform, videoId, timestamp }) {
    if (!VIDEO_URL_BUILDERS[platform]) {
      console.error(`[video-player] Unknown platform: ${platform}`);
      return;
    }

    const existingWindow = this.players.get(videoId);
    if (existingWindow && !existingWindow.isDestroyed()) {
      existingWindow.focus();
      console.log(`[video-player] Focused existing window for ${videoId}`);
      return;
    }

    const playerSession = session.fromPartition(`persist:${platform}`, {
      cache: true
    });

    const playerWindow = new BrowserWindow({
      width: 1280,
      height: 720,
      title: 'Video Player',
      webPreferences: {
        partition: `persist:${platform}`,
        session: playerSession,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });

    const url = VIDEO_URL_BUILDERS[platform]({ videoId, timestamp });
    playerWindow.loadURL(url);

    this.players.set(videoId, playerWindow);

    playerWindow.on('closed', () => {
      this.players.delete(videoId);
      console.log(`[video-player] Window closed for ${videoId}`);
    });

    console.log(`[video-player] Opened ${platform} video: ${videoId}`);
  }

  closeAll() {
    for (const [videoId, window] of this.players.entries()) {
      if (!window.isDestroyed()) {
        window.close();
      }
    }
    this.players.clear();
    console.log('[video-player] Closed all player windows');
  }
}

module.exports = { VideoPlayerManager };
