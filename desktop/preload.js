/**
 * Electron preload script - Secure IPC bridge
 *
 * Exposes safe IPC methods to the frontend via contextBridge.
 * Login events use repeatable listeners (not once) so re-login
 * works within the same desktop session.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  // Login management
  openLogin: (platform) => ipcRenderer.send('open-login', platform),
  clearLoginSession: (platform) => ipcRenderer.invoke('clear-login-session', platform),
  refreshBilibiliCookie: () => ipcRenderer.invoke('refresh-bilibili-cookie'),
  onCookieReady: (callback) => {
    const handler = (_, data) => callback(data);
    ipcRenderer.on('cookie-ready', handler);
    return () => ipcRenderer.removeListener('cookie-ready', handler);
  },
  onCookieRefreshed: (callback) => {
    const handler = (_, data) => callback(data);
    ipcRenderer.on('cookie-refreshed', handler);
    return () => ipcRenderer.removeListener('cookie-refreshed', handler);
  },

  // Video playback
  openVideoPlayer: (params) => ipcRenderer.send('open-video-player', params),
});
