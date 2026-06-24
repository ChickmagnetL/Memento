/**
 * Electron preload script - Secure IPC bridge
 *
 * Exposes safe IPC methods to the frontend via contextBridge.
 * This enables secure communication between the renderer process
 * and the main process without exposing Node.js APIs directly.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  // Login management
  openLogin: (platform) => ipcRenderer.send('open-login', platform),
  onCookieReady: (callback) => ipcRenderer.on('cookie-ready', (_, data) => callback(data)),
  onCookieRefreshed: (callback) => ipcRenderer.on('cookie-refreshed', (_, data) => callback(data)),

  // Video playback
  openVideoPlayer: (params) => ipcRenderer.send('open-video-player', params),
});
